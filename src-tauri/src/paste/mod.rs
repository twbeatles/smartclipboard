use std::thread;
use std::time::Duration;

use crate::app_state::AppState;
use crate::clipboard::internal_guard::InternalWriteGuard;
use crate::clipboard::win32::{get_sequence_number, write_clipboard_text};
use crate::errors::{AppError, Result};

const INPUT_KEYBOARD: u32 = 1;
const KEYEVENTF_KEYUP: u32 = 0x0002;
const VK_CONTROL: u16 = 0x11;
const VK_V: u16 = 0x56;

#[repr(C)]
#[allow(clippy::upper_case_acronyms)]
struct KEYBDINPUT {
    w_vk: u16,
    w_scan: u16,
    dw_flags: u32,
    time: u32,
    dw_extra_info: usize,
}

#[repr(C)]
#[allow(clippy::upper_case_acronyms)]
struct INPUT {
    r#type: u32,
    ki: KEYBDINPUT,
    padding: [u8; 16], // Ensure union size matches Windows INPUT struct (40 bytes on 64-bit)
}

#[link(name = "user32")]
extern "system" {
    fn SendInput(c_inputs: u32, p_inputs: *const INPUT, cb_size: i32) -> u32;
}

/// Simulate Ctrl+V key combination via Windows SendInput
pub fn simulate_ctrl_v() -> bool {
    let make_key = |vk: u16, flags: u32| INPUT {
        r#type: INPUT_KEYBOARD,
        ki: KEYBDINPUT {
            w_vk: vk,
            w_scan: 0,
            dw_flags: flags,
            time: 0,
            dw_extra_info: 0,
        },
        padding: [0u8; 16],
    };

    let inputs = [
        make_key(VK_CONTROL, 0),               // Ctrl Down
        make_key(VK_V, 0),                     // V Down
        make_key(VK_V, KEYEVENTF_KEYUP),       // V Up
        make_key(VK_CONTROL, KEYEVENTF_KEYUP), // Ctrl Up
    ];

    unsafe {
        let sent = SendInput(
            inputs.len() as u32,
            inputs.as_ptr(),
            std::mem::size_of::<INPUT>() as i32,
        );
        sent == inputs.len() as u32
    }
}

/// Retrieves latest item, writes to clipboard with internal guard, and simulates Ctrl+V
pub fn paste_last(state: &AppState, guard: &InternalWriteGuard) -> Result<()> {
    let items = state.db.list_history(1)?;
    if let Some(latest) = items.first() {
        if latest.r#type != "IMAGE" {
            let seq = get_sequence_number();
            guard.mark_internal(seq + 1, &latest.content);

            if write_clipboard_text(&latest.content) {
                // Short wait to allow the target focused window to read clipboard
                thread::sleep(Duration::from_millis(100));
                if simulate_ctrl_v() {
                    return Ok(());
                }
            }
        }
    }
    Err(AppError::Internal("Paste last failed".into()))
}
