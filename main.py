import argparse
import sys
from radial_qr.encoder import encode
from radial_qr.decoder import decode

def main():
    parser = argparse.ArgumentParser(description="Custom Radial QR Code Encoder/Decoder")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Encode
    parser_encode = subparsers.add_parser("encode", help="Encode text into a Radial QR")
    parser_encode.add_argument("text", help="Text to encode")
    parser_encode.add_argument("-o", "--output", default="radial_pro.png", help="Output file path")
    
    # Decode
    parser_decode = subparsers.add_parser("decode", help="Decode a Radial QR image")
    parser_decode.add_argument("image", help="Path to the image to decode")
    
    args = parser.parse_args()
    
    if args.command == "encode":
        encode(args.text, args.output)
    elif args.command == "decode":
        result = decode(args.image)
        print("\n" + "="*40)
        print("       RADIAL PRO DECODER RESULT       ")
        print("="*40)
        print(result)
        print("="*40)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
