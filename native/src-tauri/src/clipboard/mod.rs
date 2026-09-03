pub mod classifier;
pub mod copy_rules;
pub mod file_reader;
pub mod image_reader;
pub mod internal_guard;
pub mod pipeline;
pub mod win32;

pub use classifier::classify_text;
pub use copy_rules::{apply_copy_rules, CopyRule};
pub use file_reader::read_clipboard_files;
pub use image_reader::{dib_to_png, read_clipboard_image};
pub use internal_guard::InternalWriteGuard;
pub use pipeline::ClipboardPipeline;
