use std::env;
use std::process::{Command, ExitCode};

/// `chronos-cli` is a native launcher for the canonical Python CLI.
///
/// It deliberately does not emulate commands. Earlier fallbacks printed success-
/// looking messages without changing repository state, which made the native CLI
/// unsafe for scripts and misleading for operators.
fn main() -> ExitCode {
    let forwarded_args: Vec<String> = env::args().skip(1).collect();
    match delegate_to_python_cli(&forwarded_args) {
        Some(code) => ExitCode::from(code.clamp(0, 255) as u8),
        None => {
            eprintln!(
                "CHRONOS Python CLI is not available. Install the Python package first: \
                 `python -m pip install chronos-memory`, then rerun this launcher."
            );
            ExitCode::from(127)
        }
    }
}

fn delegate_to_python_cli(args: &[String]) -> Option<i32> {
    let launchers = ["python3", "python"];

    for binary in launchers {
        let mut command = Command::new(binary);
        command.args(["-m", "chronos.cli"]);
        command.args(args);

        match command.status() {
            Ok(status) if status.success() => return Some(0),
            Ok(status) => {
                // Python itself was found and executed. Preserve its real exit
                // status; never fall back to a fake native success path.
                return Some(status.code().unwrap_or(1));
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => {
                eprintln!("Failed to launch {binary}: {error}");
                return Some(1);
            }
        }
    }
    None
}
