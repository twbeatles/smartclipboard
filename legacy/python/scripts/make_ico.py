import sys
from typing import List
from PIL import Image

def main():
    if len(sys.argv) != 3:
        print("Usage: make_ico.py <input.png> <output.ico>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    try:
        img = Image.open(input_path)
        img.save(output_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"Successfully created {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
