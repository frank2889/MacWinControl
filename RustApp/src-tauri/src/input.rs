// Input module - Cross-platform mouse/keyboard control
// Uses conditional compilation for macOS and Windows

use serde::{Deserialize, Serialize};

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ScreenInfo {
    pub name: String,
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
    pub is_primary: bool,
}

// ============= macOS Implementation =============
#[cfg(target_os = "macos")]
mod platform {
    use super::ScreenInfo;
    use core_graphics::event::{CGEvent, CGEventType, CGMouseButton, CGEventTapLocation};
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use core_graphics::geometry::CGPoint;
    use core_graphics::display::{CGDisplay, CGGetActiveDisplayList};

    pub fn get_screen_size() -> (i32, i32) {
        let display = CGDisplay::main();
        (display.pixels_wide() as i32, display.pixels_high() as i32)
    }

    pub fn get_all_screens() -> Vec<ScreenInfo> {
        let mut screens = Vec::new();
        
        // Get all active displays
        let max_displays = 16u32;
        let mut display_ids = vec![0u32; max_displays as usize];
        let mut display_count = 0u32;
        
        unsafe {
            CGGetActiveDisplayList(max_displays, display_ids.as_mut_ptr(), &mut display_count);
        }
        
        let main_id = CGDisplay::main().id;
        
        for i in 0..display_count as usize {
            let display = CGDisplay::new(display_ids[i]);
            let bounds = display.bounds();
            
            screens.push(ScreenInfo {
                name: if display_ids[i] == main_id { 
                    "Main Display".to_string() 
                } else { 
                    format!("Display {}", i + 1)
                },
                x: bounds.origin.x as i32,
                y: bounds.origin.y as i32,
                width: bounds.size.width as i32,
                height: bounds.size.height as i32,
                is_primary: display_ids[i] == main_id,
            });
        }
        
        // Sort by x position (left to right)
        screens.sort_by_key(|s| s.x);
        
        screens
    }

    pub fn get_mouse_position() -> (i32, i32) {
        if let Ok(source) = CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
            if let Ok(event) = CGEvent::new(source) {
                let location = event.location();
                return (location.x as i32, location.y as i32);
            }
        }
        (0, 0)
    }

    pub fn move_mouse(x: i32, y: i32) {
        let point = CGPoint::new(x as f64, y as f64);
        if let Ok(source) = CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
            if let Ok(event) = CGEvent::new_mouse_event(
                source,
                CGEventType::MouseMoved,
                point,
                CGMouseButton::Left,
            ) {
                event.post(CGEventTapLocation::HID);
            }
        }
    }

    pub fn mouse_click(button: &str, action: &str) {
        let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
            Ok(s) => s,
            Err(_) => return,
        };
        
        let (event_type, mouse_button) = match (button, action) {
            ("left", "press") => (CGEventType::LeftMouseDown, CGMouseButton::Left),
            ("left", "release") => (CGEventType::LeftMouseUp, CGMouseButton::Left),
            ("right", "press") => (CGEventType::RightMouseDown, CGMouseButton::Right),
            ("right", "release") => (CGEventType::RightMouseUp, CGMouseButton::Right),
            ("middle", "press") => (CGEventType::OtherMouseDown, CGMouseButton::Center),
            ("middle", "release") => (CGEventType::OtherMouseUp, CGMouseButton::Center),
            _ => return,
        };
        
        let (x, y) = get_mouse_position();
        let point = CGPoint::new(x as f64, y as f64);
        
        if let Ok(event) = CGEvent::new_mouse_event(source, event_type, point, mouse_button) {
            event.post(CGEventTapLocation::HID);
        }
    }

    pub fn key_event(key_code: u32, action: &str) {
        let source = match CGEventSource::new(CGEventSourceStateID::HIDSystemState) {
            Ok(s) => s,
            Err(_) => return,
        };
        
        let keydown = action == "press";
        
        if let Ok(event) = CGEvent::new_keyboard_event(source, key_code as u16, keydown) {
            event.post(CGEventTapLocation::HID);
        }
    }

    pub fn scroll(_delta_x: i32, _delta_y: i32) {
        // Scroll not implemented yet
    }
}

// ============= Windows Implementation =============
#[cfg(target_os = "windows")]
mod platform {
    use super::ScreenInfo;
    use windows::Win32::UI::Input::KeyboardAndMouse::*;
    use windows::Win32::UI::WindowsAndMessaging::*;
    use windows::Win32::Foundation::POINT;
    use windows::Win32::Graphics::Gdi::*;

    pub fn get_screen_size() -> (i32, i32) {
        unsafe {
            let width = GetSystemMetrics(SM_CXSCREEN);
            let height = GetSystemMetrics(SM_CYSCREEN);
            (width, height)
        }
    }

    pub fn get_all_screens() -> Vec<ScreenInfo> {
        let mut screens = Vec::new();
        
        unsafe {
            // Get virtual screen bounds
            let virt_left = GetSystemMetrics(SM_XVIRTUALSCREEN);
            let virt_top = GetSystemMetrics(SM_YVIRTUALSCREEN);
            let virt_width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
            let virt_height = GetSystemMetrics(SM_CYVIRTUALSCREEN);
            let primary_width = GetSystemMetrics(SM_CXSCREEN);
            let primary_height = GetSystemMetrics(SM_CYSCREEN);
            
            // Primary monitor
            screens.push(ScreenInfo {
                name: "Primary".to_string(),
                x: 0,
                y: 0,
                width: primary_width,
                height: primary_height,
                is_primary: true,
            });
            
            // If virtual screen is larger, there are more monitors
            if virt_width > primary_width || virt_left < 0 {
                // Secondary to the left
                if virt_left < 0 {
                    screens.push(ScreenInfo {
                        name: "Secondary".to_string(),
                        x: virt_left,
                        y: 0,
                        width: -virt_left,
                        height: virt_height,
                        is_primary: false,
                    });
                }
                // Secondary to the right
                if virt_width > primary_width {
                    screens.push(ScreenInfo {
                        name: "Secondary".to_string(),
                        x: primary_width,
                        y: 0,
                        width: virt_width - primary_width,
                        height: virt_height,
                        is_primary: false,
                    });
                }
            }
        }
        
        screens.sort_by_key(|s| s.x);
        screens
    }

    pub fn get_mouse_position() -> (i32, i32) {
        unsafe {
            let mut point = POINT::default();
            let _ = GetCursorPos(&mut point);
            (point.x, point.y)
        }
    }

    pub fn move_mouse(x: i32, y: i32) {
        unsafe {
            let _ = SetCursorPos(x, y);
        }
    }

    pub fn mouse_click(button: &str, action: &str) {
        let flags = match (button, action) {
            ("left", "press") => MOUSEEVENTF_LEFTDOWN,
            ("left", "release") => MOUSEEVENTF_LEFTUP,
            ("right", "press") => MOUSEEVENTF_RIGHTDOWN,
            ("right", "release") => MOUSEEVENTF_RIGHTUP,
            ("middle", "press") => MOUSEEVENTF_MIDDLEDOWN,
            ("middle", "release") => MOUSEEVENTF_MIDDLEUP,
            _ => return,
        };
        
        let input = INPUT {
            r#type: INPUT_MOUSE,
            Anonymous: INPUT_0 {
                mi: MOUSEINPUT {
                    dx: 0,
                    dy: 0,
                    mouseData: 0,
                    dwFlags: flags,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        
        unsafe {
            SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
        }
    }

    pub fn key_event(key_code: u32, action: &str) {
        let flags = if action == "release" {
            KEYEVENTF_KEYUP
        } else {
            KEYBD_EVENT_FLAGS(0)
        };
        
        let input = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VIRTUAL_KEY(key_code as u16),
                    wScan: 0,
                    dwFlags: flags,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        
        unsafe {
            SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
        }
    }

    pub fn scroll(delta_x: i32, delta_y: i32) {
        if delta_y != 0 {
            let input = INPUT {
                r#type: INPUT_MOUSE,
                Anonymous: INPUT_0 {
                    mi: MOUSEINPUT {
                        dx: 0,
                        dy: 0,
                        mouseData: (delta_y * 120) as u32,
                        dwFlags: MOUSEEVENTF_WHEEL,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };
            unsafe { SendInput(&[input], std::mem::size_of::<INPUT>() as i32); }
        }
        
        if delta_x != 0 {
            let input = INPUT {
                r#type: INPUT_MOUSE,
                Anonymous: INPUT_0 {
                    mi: MOUSEINPUT {
                        dx: 0,
                        dy: 0,
                        mouseData: (delta_x * 120) as u32,
                        dwFlags: MOUSEEVENTF_HWHEEL,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            };
            unsafe { SendInput(&[input], std::mem::size_of::<INPUT>() as i32); }
        }
    }
}

// ============= Fallback =============
#[cfg(not(any(target_os = "macos", target_os = "windows")))]
mod platform {
    use super::ScreenInfo;
    
    pub fn get_screen_size() -> (i32, i32) { (1920, 1080) }
    pub fn get_all_screens() -> Vec<ScreenInfo> {
        vec![ScreenInfo {
            name: "Display".to_string(),
            x: 0, y: 0, width: 1920, height: 1080, is_primary: true,
        }]
    }
    pub fn get_mouse_position() -> (i32, i32) { (0, 0) }
    pub fn move_mouse(_x: i32, _y: i32) {}
    pub fn mouse_click(_button: &str, _action: &str) {}
    pub fn key_event(_key_code: u32, _action: &str) {}
    pub fn scroll(_delta_x: i32, _delta_y: i32) {}
}

pub use platform::*;
