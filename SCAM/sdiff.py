#!/usr/bin/env python3
"""
sdiff - side-by-side merge of file differences

Windows CMD compatible version with built-in diff algorithm.
No external dependencies required.
"""

import sys
import os
import subprocess
import tempfile
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

# Constants
PROGRAM_NAME = "sdiff"
VERSION = "1.0.0"
DEFAULT_WIDTH = 130
DEFAULT_EDITOR = os.environ.get("EDITOR", "notepad.exe" if os.name == 'nt' else "vi")

# Global state
tmpname: Optional[str] = None
suppress_common_lines = False


class DiffResult:
    """Represents a difference between two files"""
    def __init__(self, tag: str, i1: int, i2: int, j1: int, j2: int):
        self.tag = tag  # 'equal', 'replace', 'delete', 'insert'
        self.i1 = i1
        self.i2 = i2
        self.j1 = j1
        self.j2 = j2
    
    def left_lines(self) -> int:
        return self.i2 - self.i1
    
    def right_lines(self) -> int:
        return self.j2 - self.j1


def compute_diff(file1_lines: List[str], file2_lines: List[str]) -> List[DiffResult]:
    """Compute differences between two files using built-in difflib"""
    matcher = SequenceMatcher(None, file1_lines, file2_lines)
    results = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        results.append(DiffResult(tag, i1, i2, j1, j2))
    
    return results


def format_side_by_side(left_lines: List[str], right_lines: List[str], 
                        diff: DiffResult, width: int) -> str:
    """Format lines side-by-side for display"""
    half_width = (width - 3) // 2
    output = []
    
    left_content = left_lines[diff.i1:diff.i2] if diff.i1 < diff.i2 else []
    right_content = right_lines[diff.j1:diff.j2] if diff.j1 < diff.j2 else []
    
    max_lines = max(len(left_content), len(right_content))
    
    for i in range(max_lines):
        left_line = left_content[i].rstrip('\n') if i < len(left_content) else ""
        right_line = right_content[i].rstrip('\n') if i < len(right_content) else ""
        
        # Truncate or pad left side
        left_display = left_line[:half_width].ljust(half_width)
        
        # Determine separator
        if diff.tag == 'equal':
            separator = "   "
        elif diff.tag == 'replace':
            separator = " | "
        elif diff.tag == 'delete':
            separator = " < "
        else:  # insert
            separator = " > "
        
        # Truncate right side
        right_display = right_line[:half_width]
        
        output.append(f"{left_display}{separator}{right_display}")
    
    return '\n'.join(output)


def give_help() -> None:
    """Print help for interactive commands"""
    help_text = """
Commands:
  l or 1    Use the left version
  r or 2    Use the right version
  e         Edit a new version
  el or e1  Edit then use the left version
  er or e2  Edit then use the right version
  eb        Edit both versions
  ed        Edit both versions with headers
  s         Silent mode (suppress common lines)
  v         Verbose mode (show common lines)
  q         Quit
  ?         Show this help
"""
    print(help_text)


def edit_conflict(left_lines: List[str], lname: str, lstart: int,
                 right_lines: List[str], rname: str, rstart: int,
                 diff: DiffResult, cmd: str) -> Optional[str]:
    """Handle interactive editing of a conflict"""
    global tmpname
    
    # Create temporary file
    if not tmpname:
        fd, tmpname = tempfile.mkstemp(prefix='sdiff_', suffix='.txt')
        os.close(fd)
    
    with open(tmpname, 'w', encoding='utf-8') as tmp:
        left_content = left_lines[diff.i1:diff.i2]
        right_content = right_lines[diff.j1:diff.j2]
        
        # Write content based on command
        if cmd in ['ed', 'e1', 'el']:
            # Write left with optional header
            if cmd == 'ed' and left_content:
                if len(left_content) == 1:
                    tmp.write(f"--- {lname} line {lstart + diff.i1 + 1}\n")
                else:
                    tmp.write(f"--- {lname} lines {lstart + diff.i1 + 1}-{lstart + diff.i2}\n")
            
            for line in left_content:
                tmp.write(line)
                if not line.endswith('\n'):
                    tmp.write('\n')
        
        if cmd in ['ed', 'e2', 'er']:
            # Write right with optional header
            if cmd == 'ed' and right_content:
                if len(right_content) == 1:
                    tmp.write(f"+++ {rname} line {rstart + diff.j1 + 1}\n")
                else:
                    tmp.write(f"+++ {rname} lines {rstart + diff.j1 + 1}-{rstart + diff.j2}\n")
            
            for line in right_content:
                tmp.write(line)
                if not line.endswith('\n'):
                    tmp.write('\n')
        
        if cmd == 'eb':
            # Write both versions
            for line in left_content:
                tmp.write(line)
                if not line.endswith('\n'):
                    tmp.write('\n')
            for line in right_content:
                tmp.write(line)
                if not line.endswith('\n'):
                    tmp.write('\n')
    
    # Launch editor
    editor = os.environ.get('EDITOR', DEFAULT_EDITOR)
    try:
        subprocess.run([editor, tmpname], check=True)
    except subprocess.CalledProcessError:
        print(f"Warning: Editor exited with error", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: Editor '{editor}' not found", file=sys.stderr)
        print(f"Set EDITOR environment variable or edit {tmpname} manually", file=sys.stderr)
        input("Press Enter when done editing...")
    
    # Read edited content
    try:
        with open(tmpname, 'r', encoding='utf-8') as tmp:
            return tmp.read()
    except Exception as e:
        print(f"Error reading edited file: {e}", file=sys.stderr)
        return None


def interactive_merge(left_lines: List[str], lname: str,
                     right_lines: List[str], rname: str,
                     diffs: List[DiffResult], width: int) -> Optional[str]:
    """Perform interactive merge"""
    global suppress_common_lines
    
    result = []
    
    for diff in diffs:
        if diff.tag == 'equal':
            # Identical lines
            if not suppress_common_lines:
                print(format_side_by_side(left_lines, right_lines, diff, width))
            
            # Add to result
            for line in left_lines[diff.i1:diff.i2]:
                result.append(line)
        
        else:
            # Conflict - requires user decision
            print("\n" + "=" * width)
            print("CONFLICT:")
            print(format_side_by_side(left_lines, right_lines, diff, width))
            print("=" * width)
            
            # Get user command
            while True:
                try:
                    cmd = input("\nChoice [l/r/e/el/er/eb/ed/s/v/q/?]: ").strip().lower()
                except EOFError:
                    return None
                
                if cmd in ['l', '1']:
                    # Use left version
                    for line in left_lines[diff.i1:diff.i2]:
                        result.append(line)
                    break
                
                elif cmd in ['r', '2']:
                    # Use right version
                    for line in right_lines[diff.j1:diff.j2]:
                        result.append(line)
                    break
                
                elif cmd == 's':
                    suppress_common_lines = True
                    print("Silent mode enabled")
                    continue
                
                elif cmd == 'v':
                    suppress_common_lines = False
                    print("Verbose mode enabled")
                    continue
                
                elif cmd == 'q':
                    return None
                
                elif cmd in ['e', 'e1', 'el', 'e2', 'er', 'eb', 'ed']:
                    edited = edit_conflict(left_lines, lname, 0,
                                          right_lines, rname, 0,
                                          diff, cmd)
                    if edited is not None:
                        result.append(edited)
                        break
                    else:
                        print("Edit cancelled")
                        continue
                
                elif cmd == '?':
                    give_help()
                    continue
                
                else:
                    print("Invalid command. Type ? for help.")
                    continue
    
    return ''.join(result)


def simple_diff_display(left_lines: List[str], right_lines: List[str],
                       diffs: List[DiffResult], width: int) -> None:
    """Display differences without interaction"""
    global suppress_common_lines
    
    for diff in diffs:
        if diff.tag == 'equal' and suppress_common_lines:
            continue
        
        output = format_side_by_side(left_lines, right_lines, diff, width)
        if output:
            print(output)


def main() -> int:
    """Main entry point"""
    global suppress_common_lines, tmpname
    
    import argparse
    
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description='Side-by-side merge of differences between FILE1 and FILE2.'
    )
    
    parser.add_argument('file1', help='First file to compare')
    parser.add_argument('file2', help='Second file to compare')
    parser.add_argument('-o', '--output', help='Output file for interactive mode')
    parser.add_argument('-s', '--suppress-common-lines', action='store_true',
                       help='Do not output common lines')
    parser.add_argument('-w', '--width', type=int, default=DEFAULT_WIDTH,
                       help=f'Output width in columns (default: {DEFAULT_WIDTH})')
    parser.add_argument('-v', '--version', action='version',
                       version=f'{PROGRAM_NAME} {VERSION}')
    
    args = parser.parse_args()
    
    suppress_common_lines = args.suppress_common_lines
    
    # Read input files
    try:
        with open(args.file1, 'r', encoding='utf-8', errors='replace') as f:
            left_lines = f.readlines()
    except Exception as e:
        print(f"Error reading {args.file1}: {e}", file=sys.stderr)
        return 2
    
    try:
        with open(args.file2, 'r', encoding='utf-8', errors='replace') as f:
            right_lines = f.readlines()
    except Exception as e:
        print(f"Error reading {args.file2}: {e}", file=sys.stderr)
        return 2
    
    # Compute differences
    diffs = compute_diff(left_lines, right_lines)
    
    # Check if files are identical
    all_equal = all(d.tag == 'equal' for d in diffs)
    
    try:
        if args.output:
            # Interactive mode
            result = interactive_merge(left_lines, args.file1,
                                     right_lines, args.file2,
                                     diffs, args.width)
            
            if result is None:
                print("\nMerge cancelled", file=sys.stderr)
                return 2
            
            # Write output
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"\nOutput written to {args.output}")
            except Exception as e:
                print(f"Error writing to {args.output}: {e}", file=sys.stderr)
                return 2
        
        else:
            # Display-only mode
            simple_diff_display(left_lines, right_lines, diffs, args.width)
    
    finally:
        # Cleanup temp file
        if tmpname and os.path.exists(tmpname):
            try:
                os.unlink(tmpname)
            except:
                pass
    
    # Return appropriate exit code
    return 0 if all_equal else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        if tmpname and os.path.exists(tmpname):
            try:
                os.unlink(tmpname)
            except:
                pass
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
