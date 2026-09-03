use std::ptr::null_mut;
use super::win32::CF_HDROP;
use crate::database::file_paths::normalize_local_file_paths;

#[link(name = "user32")]
extern "system" {
    fn OpenClipboard(hwnd: isize) -> i32;
    fn CloseClipboard() -> i32;
    fn GetClipboardData(format: u32) -> isize;
    fn IsClipboardFormatAvailable(format: u32) -> i32;
}

#[link(name = "shell32")]
extern "system" {
    fn DragQueryFileW(hdrop: isize, i_file: u32, lpsz_file: *mut u16, cch: u32) -> u32;
}

/// Reads CF_HDROP copied files from Windows Explorer
pub fn read_clipboard_files() -> Option<Vec<String>> {
    unsafe {
        if IsClipboardFormatAvailable(CF_HDROP) == 0 {
            return None;
        }

        if OpenClipboard(0) != 0 {
            let hdrop = GetClipboardData(CF_HDROP);
            if hdrop != 0 {
                let file_count = DragQueryFileW(hdrop, 0xFFFFFFFF, null_mut(), 0);
                if file_count > 0 {
                    let mut raw_paths = Vec::with_capacity(file_count as usize);
                    let mut buf = vec![0u16; 1024];

                    for i in 0..file_count {
                        let len = DragQueryFileW(hdrop, i, buf.as_mut_ptr(), buf.len() as u32);
                        if len > 0 {
                            let path_str = String::from_utf16_lossy(&buf[..len as usize]);
                            raw_paths.push(path_str);
                        }
                    }

                    CloseClipboard();
                    let normalized = normalize_local_file_paths(&raw_paths);
                    if !normalized.is_empty() {
                        return Some(normalized);
                    }
                    return None;
                }
            }
            CloseClipboard();
        }
    }
    None
}
