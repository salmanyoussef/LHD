//To implement
file1 = ["Matt", "John", "Tom"]
file2 = ["Matt", "Sam", "Brad", "Adam"]

max_lines = max(len(file1), len(file2))

for i in range(max_lines)
  line1 = file1[i] if i < len(file1) else None
  line2 = file2[i] if i < len(file2) else None

  if line1 == line2
    print(f" Line {i+1}: same -> {line1}")
  elif line1 is None:
    print(f"+ Line {i+1}: added -> {line2}")
  elif line2 is None:
    print(f"- Line {i+1}: removed -> {line1}")
  else:
    print(f"~ Line {i+1}: changed from '{line1}' to '{line2}'")
  
  
