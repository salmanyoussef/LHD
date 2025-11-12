#!/usr/bin/env python3
"""
GNU sdiff - side-by-side merge of file differences

Python implementation of the sdiff utility from GNU diffutils.
"""

import sys
import os
import signal
import subprocess
import tempfile
import argparse
import shutil
from pathlib import Path
from typing import Optional, List, BinaryIO, TextIO

# Constants
PROGRAM_NAME = "sdiff"
VERSION = "1.0.0"
SDIFF_BUFSIZE = 65536
DEFAULT_DIFF_PROGRAM = "diff"
DEFAULT_EDITOR = os.environ.get("EDITOR", "vi")

# Global state
tmpname: Optional[str] = None
tmp: Optional[TextIO] = None
diffpid: Optional[int] = None
suppress_common_lines = False
signal_received: Optional[int] = None
ignore_SIGINT = False
sigs_trapped = False


class LineFilter:
    """Buffer for reading lines from a file"""
    
    def __init__(self, infile: BinaryIO):
        self.infile = infile
        self.buffer = bytearray()
        self.bufpos = 0
    
    def refill(self) -> int:
        """Fill buffer from input file"""
        data = self.infile.read(SDIFF_BUFSIZE)
        if data:
            self.buffer = bytearray(data)
            self.bufpos = 0
            return len(data)
        return 0
    
    def copy(self, lines: int, outfile: BinaryIO) -> None:
        """Copy specified number of lines to output file"""
        while lines > 0:
            # Find newline
            try:
                newline_pos = self.buffer.index(b'\n', self.bufpos)
                outfile.write(self.buffer[self.bufpos:newline_pos + 1])
                self.bufpos = newline_pos + 1
                lines -= 1
            except ValueError:
                # No newline in current buffer
                outfile.write(self.buffer[self.bufpos:])
                if not self.refill():
                    return
    
    def skip(self, lines: int) -> None:
        """Skip specified number of lines"""
        while lines > 0:
            try:
                newline_pos = self.buffer.index(b'\n', self.bufpos)
                self.bufpos = newline_pos + 1
                lines -= 1
            except ValueError:
                if not self.refill():
                    break
    
    def snarf(self, max_size: int) -> Optional[str]:
        """Read a line into string, return None on EOF"""
        result = bytearray()
        
        while True:
            try:
                newline_pos = self.buffer.index(b'\n', self.bufpos)
                line_data = self.buffer[self.bufpos:newline_pos]
                
                if len(result) + len(line_data) > max_size:
                    return None
                
                result.extend(line_data)
                self.bufpos = newline_pos + 1
                return result.decode('utf-8', errors='replace')
            except ValueError:
                result.extend(self.buffer[self.bufpos:])
                if not self.refill():
                    return result.decode('utf-8', errors='replace') if result else None


def cleanup(signo: Optional[int] = None) -> None:
    """Clean up temporary files and processes"""
    global diffpid, tmpname
    
    if diffpid and diffpid > 0:
        try:
            os.kill(diffpid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    
    if tmpname and os.path.exists(tmpname):
        try:
            os.unlink(tmpname)
        except OSError:
            pass


def signal_handler(signum: int, frame) -> None:
    """Handle signals"""
    global signal_received, ignore_SIGINT
    
    if not (signum == signal.SIGINT and ignore_SIGINT):
        signal_received = signum


def trap_signals() -> None:
    """Set up signal handlers"""
    global sigs_trapped
    
    signals_to_trap = [signal.SIGINT, signal.SIGTERM]
    
    if hasattr(signal, 'SIGHUP'):
        signals_to_trap.append(signal.SIGHUP)
    if hasattr(signal, 'SIGQUIT'):
        signals_to_trap.append(signal.SIGQUIT)
    
    for sig in signals_to_trap:
        signal.signal(sig, signal_handler)
    
    sigs_trapped = True


def check_signals() -> None:
    """Exit if a signal was received"""
    if signal_received:
        cleanup()
        sys.exit(2)


def give_help() -> None:
    """Print help for interactive commands"""
    help_text = """
ed:	Edit then use both versions, each decorated with a header.
eb:	Edit then use both versions.
el or e1:	Edit then use the left version.
er or e2:	Edit then use the right version.
e:	Discard both versions then edit a new one.
l or 1:	Use the left version.
r or 2:	Use the right version.
s:	Silently include common lines.
v:	Verbosely include common lines.
q:	Quit.
"""
    print(help_text, file=sys.stderr)


def edit(left: LineFilter, lname: str, lline: int, llen: int,
         right: LineFilter, rname: str, rline: int, rlen: int,
         outfile: BinaryIO) -> bool:
    """Handle interactive editing of differences"""
    global tmpname, tmp, suppress_common_lines, ignore_SIGINT
    
    while True:
        gotcmd = False
        
        while not gotcmd:
            print("% ", end='', flush=True)
            
            try:
                line = input().strip()
            except EOFError:
                return False
            
            if not line:
                give_help()
                continue
            
            cmd = line[0]
            
            # Handle two-character commands (e1, e2, eb, ed, el, er)
            if cmd == 'e' and len(line) > 1:
                cmd = cmd + line[1]
            
            if cmd in ['1', 'l', '2', 'r', 's', 'v', 'q'] or \
               cmd in ['e', 'e1', 'e2', 'eb', 'ed', 'el', 'er']:
                gotcmd = True
            else:
                give_help()
        
        # Execute command
        if cmd in ['1', 'l']:
            left.copy(llen, outfile)
            right.skip(rlen)
            return True
        
        elif cmd in ['2', 'r']:
            right.copy(rlen, outfile)
            left.skip(llen)
            return True
        
        elif cmd == 's':
            suppress_common_lines = True
        
        elif cmd == 'v':
            suppress_common_lines = False
        
        elif cmd == 'q':
            return False
        
        elif cmd in ['e', 'e1', 'e2', 'eb', 'ed', 'el', 'er']:
            # Create temporary file
            if tmpname:
                tmp = open(tmpname, 'w')
            else:
                fd, tmpname = tempfile.mkstemp(prefix='sdiff')
                tmp = os.fdopen(fd, 'w')
            
            # Write content based on command
            if cmd in ['ed']:
                if llen:
                    if llen == 1:
                        tmp.write(f"--- {lname} {lline}\n")
                    else:
                        tmp.write(f"--- {lname} {lline},{lline + llen - 1}\n")
            
            if cmd in ['e1', 'eb', 'el', 'ed']:
                # Copy left content to temp file
                left_data = bytearray()
                for _ in range(llen):
                    try:
                        newline_pos = left.buffer.index(b'\n', left.bufpos)
                        left_data.extend(left.buffer[left.bufpos:newline_pos + 1])
                        left.bufpos = newline_pos + 1
                    except ValueError:
                        left.refill()
                tmp.write(left_data.decode('utf-8', errors='replace'))
            else:
                left.skip(llen)
            
            if cmd in ['ed']:
                if rlen:
                    if rlen == 1:
                        tmp.write(f"+++ {rname} {rline}\n")
                    else:
                        tmp.write(f"+++ {rname} {rline},{rline + rlen - 1}\n")
            
            if cmd in ['e2', 'eb', 'er', 'ed']:
                # Copy right content to temp file
                right_data = bytearray()
                for _ in range(rlen):
                    try:
                        newline_pos = right.buffer.index(b'\n', right.bufpos)
                        right_data.extend(right.buffer[right.bufpos:newline_pos + 1])
                        right.bufpos = newline_pos + 1
                    except ValueError:
                        right.refill()
                tmp.write(right_data.decode('utf-8', errors='replace'))
            else:
                right.skip(rlen)
            
            tmp.close()
            
            # Launch editor
            ignore_SIGINT = True
            check_signals()
            
            editor = os.environ.get('EDITOR', DEFAULT_EDITOR)
            result = subprocess.run([editor, tmpname])
            
            ignore_SIGINT = False
            
            if result.returncode != 0:
                print(f"Editor exited with status {result.returncode}", file=sys.stderr)
            
            # Copy edited content to output
            with open(tmpname, 'rb') as tmp:
                shutil.copyfileobj(tmp, outfile)
            
            return True


def interact(diff: LineFilter, left: LineFilter, lname: str,
             right: LineFilter, rname: str, outfile: BinaryIO) -> bool:
    """Handle interactive merging"""
    lline = 1
    rline = 1
    
    while True:
        diff_help = diff.snarf(256)
        
        if diff_help is None:
            return False
        
        if not diff_help:
            return True
        
        check_signals()
        
        if diff_help[0] == ' ':
            print(diff_help[1:])
        else:
            # Parse command: "c,llen,rlen" or "i,llen,rlen"
            parts = diff_help.split(',')
            if len(parts) != 3:
                print(f"Invalid diff help: {diff_help}", file=sys.stderr)
                return False
            
            cmd = parts[0][0]
            llen = int(parts[1])
            rlen = int(parts[2])
            lenmax = max(llen, rlen)
            
            if cmd == 'i':
                # Identical lines
                if not suppress_common_lines:
                    diff.copy(lenmax, sys.stdout.buffer)
                else:
                    diff.skip(lenmax)
                
                left.copy(llen, outfile)
                right.skip(rlen)
            
            elif cmd == 'c':
                # Changed lines - interactive editing
                diff.copy(lenmax, sys.stdout.buffer)
                if not edit(left, lname, lline, llen,
                           right, rname, rline, rlen, outfile):
                    return False
            
            lline += llen
            rline += rlen


def main() -> int:
    """Main entry point"""
    global suppress_common_lines
    
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description='Side-by-side merge of differences between FILE1 and FILE2.'
    )
    
    parser.add_argument('file1', help='First file to compare')
    parser.add_argument('file2', help='Second file to compare')
    parser.add_argument('-o', '--output', help='Output file for interactive mode')
    parser.add_argument('-s', '--suppress-common-lines', action='store_true',
                       help='Do not output common lines')
    parser.add_argument('-w', '--width', type=int, default=130,
                       help='Output at most NUM print columns')
    parser.add_argument('-l', '--left-column', action='store_true',
                       help='Output only the left column of common lines')
    parser.add_argument('-i', '--ignore-case', action='store_true',
                       help='Ignore case differences')
    parser.add_argument('-b', '--ignore-space-change', action='store_true',
                       help='Ignore changes in whitespace')
    parser.add_argument('-W', '--ignore-all-space', action='store_true',
                       help='Ignore all whitespace')
    parser.add_argument('-B', '--ignore-blank-lines', action='store_true',
                       help='Ignore blank line changes')
    parser.add_argument('-t', '--expand-tabs', action='store_true',
                       help='Expand tabs to spaces')
    parser.add_argument('-v', '--version', action='version',
                       version=f'{PROGRAM_NAME} {VERSION}')
    
    args = parser.parse_args()
    
    suppress_common_lines = args.suppress_common_lines
    
    # Build diff command arguments
    diff_args = [DEFAULT_DIFF_PROGRAM]
    
    if args.ignore_case:
        diff_args.append('-i')
    if args.ignore_space_change:
        diff_args.append('-b')
    if args.ignore_all_space:
        diff_args.append('-w')
    if args.ignore_blank_lines:
        diff_args.append('-B')
    if args.expand_tabs:
        diff_args.append('-t')
    if args.left_column:
        diff_args.append('--left-column')
    
    if not args.output:
        # Non-interactive mode - just run diff
        if suppress_common_lines:
            diff_args.append('--suppress-common-lines')
        diff_args.extend(['-y', '-W', str(args.width), '--', args.file1, args.file2])
        os.execvp(diff_args[0], diff_args)
    else:
        # Interactive mode
        diff_args.extend(['--sdiff-merge-assist', '--', args.file1, args.file2])
        
        trap_signals()
        
        # Start diff process
        diff_proc = subprocess.Popen(
            diff_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        global diffpid
        diffpid = diff_proc.pid
        
        # Open files
        with open(args.file1, 'rb') as left_file, \
             open(args.file2, 'rb') as right_file, \
             open(args.output, 'wb') as out_file:
            
            diff_filter = LineFilter(diff_proc.stdout)
            left_filter = LineFilter(left_file)
            right_filter = LineFilter(right_file)
            
            success = interact(diff_filter, left_filter, args.file1,
                             right_filter, args.file2, out_file)
        
        # Wait for diff to complete
        diff_proc.wait()
        
        if tmpname and os.path.exists(tmpname):
            os.unlink(tmpname)
        
        if not success:
            return 2
        
        return diff_proc.returncode if diff_proc.returncode <= 1 else 2
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        cleanup()
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        cleanup()
        sys.exit(2)