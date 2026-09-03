use std::io::Cursor;
use image::{ImageFormat, RgbaImage};

use super::win32::CF_DIB;

#[link(name = "user32")]
extern "system" {
    fn OpenClipboard(hwnd: isize) -> i32;
    fn CloseClipboard() -> i32;
    fn GetClipboardData(format: u32) -> isize;
    fn IsClipboardFormatAvailable(format: u32) -> i32;
}

#[link(name = "kernel32")]
extern "system" {
    fn GlobalLock(hmem: isize) -> *mut std::ffi::c_void;
    fn GlobalUnlock(hmem: isize) -> i32;
    fn GlobalSize(hmem: isize) -> usize;
}

const MAX_IMAGE_CLIPBOARD_BYTES: usize = 20 * 1024 * 1024; // 20 MB

/// Reads CF_DIB image from Windows clipboard and encodes as standard PNG bytes
pub fn read_clipboard_image() -> Option<Vec<u8>> {
    unsafe {
        if IsClipboardFormatAvailable(CF_DIB) == 0 {
            return None;
        }

        if OpenClipboard(0) != 0 {
            let handle = GetClipboardData(CF_DIB);
            if handle != 0 {
                let size = GlobalSize(handle);
                if size > 40 && size <= MAX_IMAGE_CLIPBOARD_BYTES {
                    let ptr = GlobalLock(handle) as *const u8;
                    if !ptr.is_null() {
                        let data = std::slice::from_raw_parts(ptr, size);
                        let png_bytes = dib_to_png(data);
                        GlobalUnlock(handle);
                        CloseClipboard();
                        return png_bytes;
                    }
                }
            }
            CloseClipboard();
        }
    }
    None
}

/// Converts raw DIB byte buffer (BITMAPINFOHEADER + pixels) to PNG bytes
pub fn dib_to_png(dib: &[u8]) -> Option<Vec<u8>> {
    if dib.len() < 40 {
        return None;
    }

    let header_size = u32::from_le_bytes(dib[0..4].try_into().ok()?) as usize;
    let width = i32::from_le_bytes(dib[4..8].try_into().ok()?);
    let height = i32::from_le_bytes(dib[8..12].try_into().ok()?);
    let bit_count = u16::from_le_bytes(dib[14..16].try_into().ok()?);
    let compression = u32::from_le_bytes(dib[16..20].try_into().ok()?);

    if width <= 0 || height == 0 || header_size < 40 || compression != 0 {
        return None;
    }

    let abs_height = height.unsigned_abs();
    let is_top_down = height < 0;
    let mut img = RgbaImage::new(width as u32, abs_height);

    let pixel_offset = header_size;
    if pixel_offset >= dib.len() {
        return None;
    }
    let pixel_data = &dib[pixel_offset..];

    if bit_count == 32 {
        let row_stride = (width as usize) * 4;
        for y in 0..abs_height {
            let src_y = if is_top_down { y as usize } else { (abs_height - 1 - y) as usize };
            let row_start = src_y * row_stride;
            if row_start + row_stride > pixel_data.len() {
                break;
            }
            for x in 0..(width as u32) {
                let px_idx = row_start + (x as usize) * 4;
                let b = pixel_data[px_idx];
                let g = pixel_data[px_idx + 1];
                let r = pixel_data[px_idx + 2];
                let a = pixel_data[px_idx + 3];
                // Handle alpha=0 as fully opaque if all alphas are 0 (common Windows GDI quirk)
                let final_a = if a == 0 { 255 } else { a };
                img.put_pixel(x, y, image::Rgba([r, g, b, final_a]));
            }
        }
    } else if bit_count == 24 {
        let row_stride = (width as usize * 3).div_ceil(4) * 4; // 4-byte aligned
        for y in 0..abs_height {
            let src_y = if is_top_down { y as usize } else { (abs_height - 1 - y) as usize };
            let row_start = src_y * row_stride;
            if row_start + (width as usize * 3) > pixel_data.len() {
                break;
            }
            for x in 0..(width as u32) {
                let px_idx = row_start + (x as usize) * 3;
                let b = pixel_data[px_idx];
                let g = pixel_data[px_idx + 1];
                let r = pixel_data[px_idx + 2];
                img.put_pixel(x, y, image::Rgba([r, g, b, 255]));
            }
        }
    } else {
        return None;
    }

    let mut out = Vec::new();
    let mut cursor = Cursor::new(&mut out);
    img.write_to(&mut cursor, ImageFormat::Png).ok()?;
    Some(out)
}
