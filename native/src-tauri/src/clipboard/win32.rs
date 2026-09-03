use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use std::ptr::null_mut;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;

pub const CF_UNICODETEXT: u32 = 13;
pub const CF_HDROP: u32 = 15;
pub const CF_DIB: u32 = 8;
pub const WM_CLIPBOARDUPDATE: u32 = 0x031D;
const GMEM_MOVEABLE: u32 = 0x0002;
const HWND_MESSAGE: isize = -3;

#[repr(C)]
#[allow(clippy::upper_case_acronyms)]
struct WNDCLASSW {
    style: u32,
    lpfn_wnd_proc: unsafe extern "system" fn(isize, u32, usize, isize) -> isize,
    cb_cls_extra: i32,
    cb_wnd_extra: i32,
    h_instance: isize,
    h_icon: isize,
    h_cursor: isize,
    hbr_background: isize,
    lpsz_menu_name: *const u16,
    lpsz_class_name: *const u16,
}

#[repr(C)]
#[allow(clippy::upper_case_acronyms)]
struct POINT {
    x: i32,
    y: i32,
}

#[repr(C)]
#[allow(clippy::upper_case_acronyms)]
struct MSG {
    hwnd: isize,
    message: u32,
    w_param: usize,
    l_param: isize,
    time: u32,
    pt: POINT,
}

#[link(name = "user32")]
extern "system" {
    fn GetClipboardSequenceNumber() -> u32;
    fn OpenClipboard(hwnd: isize) -> i32;
    fn CloseClipboard() -> i32;
    fn EmptyClipboard() -> i32;
    fn GetClipboardData(format: u32) -> isize;
    fn SetClipboardData(format: u32, hmem: isize) -> isize;
    #[allow(dead_code)]
    fn IsClipboardFormatAvailable(format: u32) -> i32;
    fn AddClipboardFormatListener(hwnd: isize) -> i32;
    fn RemoveClipboardFormatListener(hwnd: isize) -> i32;
    fn RegisterClassW(lp_wnd_class: *const WNDCLASSW) -> u16;
    fn CreateWindowExW(
        dw_ex_style: u32,
        lp_class_name: *const u16,
        lp_window_name: *const u16,
        dw_style: u32,
        x: i32,
        y: i32,
        n_width: i32,
        n_height: i32,
        h_wnd_parent: isize,
        h_menu: isize,
        h_instance: isize,
        lp_param: *mut std::ffi::c_void,
    ) -> isize;
    fn DestroyWindow(hwnd: isize) -> i32;
    fn DefWindowProcW(hwnd: isize, msg: u32, w_param: usize, l_param: isize) -> isize;
    fn GetMessageW(lp_msg: *mut MSG, hwnd: isize, w_msg_filter_min: u32, w_msg_filter_max: u32) -> i32;
    fn TranslateMessage(lp_msg: *const MSG) -> i32;
    fn DispatchMessageW(lp_msg: *const MSG) -> isize;
    fn PostMessageW(hwnd: isize, msg: u32, w_param: usize, l_param: isize) -> i32;
}

#[link(name = "kernel32")]
extern "system" {
    fn GlobalLock(hmem: isize) -> *mut std::ffi::c_void;
    fn GlobalUnlock(hmem: isize) -> i32;
    fn GlobalAlloc(flags: u32, bytes: usize) -> isize;
    fn GlobalFree(hmem: isize) -> isize;
    fn GetModuleHandleW(lp_module_name: *const u16) -> isize;
}

pub fn get_sequence_number() -> u32 {
    unsafe { GetClipboardSequenceNumber() }
}

fn to_wide(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(Some(0)).collect()
}

/// Reads CF_UNICODETEXT from Windows clipboard with bounded retry
pub fn read_clipboard_text() -> Option<String> {
    for _ in 0..5 {
        unsafe {
            if OpenClipboard(0) != 0 {
                let handle = GetClipboardData(CF_UNICODETEXT);
                if handle != 0 {
                    let ptr = GlobalLock(handle) as *const u16;
                    if !ptr.is_null() {
                        let mut len = 0;
                        while *ptr.add(len) != 0 {
                            len += 1;
                        }
                        let slice = std::slice::from_raw_parts(ptr, len);
                        let text = String::from_utf16_lossy(slice);
                        GlobalUnlock(handle);
                        CloseClipboard();
                        return Some(text);
                    }
                }
                CloseClipboard();
                return None;
            }
        }
        thread::sleep(std::time::Duration::from_millis(20));
    }
    None
}

/// Writes CF_UNICODETEXT to Windows clipboard
pub fn write_clipboard_text(text: &str) -> bool {
    let wide = to_wide(text);
    let bytes_len = wide.len() * 2;

    unsafe {
        for _ in 0..5 {
            if OpenClipboard(0) != 0 {
                EmptyClipboard();
                let hmem = GlobalAlloc(GMEM_MOVEABLE, bytes_len);
                if hmem != 0 {
                    let ptr = GlobalLock(hmem) as *mut u16;
                    if !ptr.is_null() {
                        std::ptr::copy_nonoverlapping(wide.as_ptr(), ptr, wide.len());
                        GlobalUnlock(hmem);
                        SetClipboardData(CF_UNICODETEXT, hmem);
                    } else {
                        GlobalFree(hmem);
                    }
                }
                CloseClipboard();
                return true;
            }
            thread::sleep(std::time::Duration::from_millis(20));
        }
    }
    false
}

static CALLBACK: std::sync::OnceLock<Box<dyn Fn() + Send + Sync>> = std::sync::OnceLock::new();

unsafe extern "system" fn window_proc(
    hwnd: isize,
    msg: u32,
    w_param: usize,
    l_param: isize,
) -> isize {
    match msg {
        WM_CLIPBOARDUPDATE => {
            if let Some(cb) = CALLBACK.get() {
                cb();
            }
            0
        }
        _ => DefWindowProcW(hwnd, msg, w_param, l_param),
    }
}

pub struct ClipboardListenerHandle {
    running: Arc<AtomicBool>,
    hwnd: isize,
}

impl Drop for ClipboardListenerHandle {
    fn drop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if self.hwnd != 0 {
            unsafe {
                RemoveClipboardFormatListener(self.hwnd);
                PostMessageW(self.hwnd, 0x0012 /* WM_QUIT */, 0, 0);
            }
        }
    }
}

/// Starts an event-driven Windows clipboard listener using AddClipboardFormatListener
pub fn start_clipboard_listener<F>(callback: F) -> ClipboardListenerHandle
where
    F: Fn() + Send + Sync + 'static,
{
    let _ = CALLBACK.set(Box::new(callback));

    let running = Arc::new(AtomicBool::new(true));
    let (tx, rx) = std::sync::mpsc::channel();

    let r_clone = running.clone();
    thread::spawn(move || unsafe {
        let class_name = to_wide("SmartClipboardListenerClass");
        let h_instance = GetModuleHandleW(null_mut());

        let wnd_class = WNDCLASSW {
            style: 0,
            lpfn_wnd_proc: window_proc,
            cb_cls_extra: 0,
            cb_wnd_extra: 0,
            h_instance,
            h_icon: 0,
            h_cursor: 0,
            hbr_background: 0,
            lpsz_menu_name: null_mut(),
            lpsz_class_name: class_name.as_ptr(),
        };

        RegisterClassW(&wnd_class);

        let hwnd = CreateWindowExW(
            0,
            class_name.as_ptr(),
            class_name.as_ptr(),
            0,
            0,
            0,
            0,
            0,
            HWND_MESSAGE,
            0,
            h_instance,
            null_mut(),
        );

        if hwnd != 0 {
            AddClipboardFormatListener(hwnd);
            let _ = tx.send(hwnd);

            let mut msg: MSG = std::mem::zeroed();
            while r_clone.load(Ordering::SeqCst) && GetMessageW(&mut msg, 0, 0, 0) > 0 {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
            RemoveClipboardFormatListener(hwnd);
            DestroyWindow(hwnd);
        } else {
            let _ = tx.send(0);
        }
    });

    let hwnd = rx.recv().unwrap_or(0);
    ClipboardListenerHandle { running, hwnd }
}
