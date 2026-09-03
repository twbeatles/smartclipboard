use smartclipboard_native_lib::clipboard::dib_to_png;
use smartclipboard_native_lib::database::file_paths::{
    file_signature_from_paths, normalize_local_file_paths,
};

#[test]
fn test_file_signature_and_normalize_parity() {
    let raw = vec![
        r"C:\Users\TEST\Documents\file2.txt".to_string(),
        r"c:/users/test/documents/file1.txt".to_string(),
    ];

    let normalized = normalize_local_file_paths(&raw);
    assert_eq!(normalized.len(), 2);
    assert_eq!(normalized[0], r"C:\Users\TEST\Documents\file2.txt");
    assert_eq!(normalized[1], r"c:\users\test\documents\file1.txt");

    let sig1 = file_signature_from_paths(&raw);
    // Permuted and case altered
    let raw_reversed = vec![
        r"C:/users/test/documents/file1.txt".to_string(),
        r"c:\users\test\documents\file2.txt".to_string(),
    ];
    let sig2 = file_signature_from_paths(&raw_reversed);
    assert_eq!(sig1, sig2, "Signatures must be deterministic and order/case invariant");
    assert_eq!(sig1.len(), 64, "SHA-256 hex digest length must be 64");
}

#[test]
fn test_dib_to_png_conversion() {
    // Construct minimal 2x2 24-bit DIB byte buffer
    let mut dib = Vec::new();
    // BITMAPINFOHEADER: size=40, width=2, height=2, planes=1, bitCount=24, compression=0, sizeImage=16
    dib.extend_from_slice(&40u32.to_le_bytes()); // biSize
    dib.extend_from_slice(&2i32.to_le_bytes());  // biWidth
    dib.extend_from_slice(&2i32.to_le_bytes());  // biHeight
    dib.extend_from_slice(&1u16.to_le_bytes());  // biPlanes
    dib.extend_from_slice(&24u16.to_le_bytes()); // biBitCount
    dib.extend_from_slice(&0u32.to_le_bytes());  // biCompression
    dib.extend_from_slice(&16u32.to_le_bytes()); // biSizeImage
    dib.extend_from_slice(&0i32.to_le_bytes());  // biXPelsPerMeter
    dib.extend_from_slice(&0i32.to_le_bytes());  // biYPelsPerMeter
    dib.extend_from_slice(&0u32.to_le_bytes());  // biClrUsed
    dib.extend_from_slice(&0u32.to_le_bytes());  // biClrImportant

    // Pixel data: 2 rows of 2 pixels (BGR), each row padded to 8 bytes (4-byte alignment: 2*3=6 -> 8)
    // Row 0
    dib.extend_from_slice(&[255, 0, 0, 0, 255, 0, 0, 0]); // Blue px, Green px, 2 bytes pad
    // Row 1
    dib.extend_from_slice(&[0, 0, 255, 255, 255, 255, 0, 0]); // Red px, White px, 2 bytes pad

    let png_opt = dib_to_png(&dib);
    assert!(png_opt.is_some(), "DIB to PNG conversion should succeed");
    let png_bytes = png_opt.unwrap();

    // Verify PNG magic signature: 0x89 'P' 'N' 'G' '\r' '\n' 0x1A '\n'
    let magic = [0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A];
    assert_eq!(&png_bytes[0..8], &magic, "Converted bytes must have valid PNG magic");
}
