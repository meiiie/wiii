use std::{env, fs, io, io::Read, process};
use wiii_desktop_lib::realtime_motor::{evaluate_motor_pack, MotorHostProbe, MotorPackArtifact};

fn main() {
    let input = if let Some(path) = env::args_os().nth(1) {
        fs::read_to_string(path).unwrap_or_else(|error| {
            eprintln!("failed to read Motor host probe: {error}");
            process::exit(2);
        })
    } else {
        let mut input = String::new();
        io::stdin()
            .read_to_string(&mut input)
            .unwrap_or_else(|error| {
                eprintln!("failed to read Motor host probe from stdin: {error}");
                process::exit(2);
            });
        input
    };
    let probe = serde_json::from_str::<MotorHostProbe>(&input).unwrap_or_else(|error| {
        eprintln!("failed to parse Motor host probe: {error}");
        process::exit(2);
    });
    let report =
        evaluate_motor_pack(MotorPackArtifact::open_p2p_150m(), probe).unwrap_or_else(|error| {
            eprintln!("failed to evaluate Motor host probe: {error}");
            process::exit(2);
        });
    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("preflight report must serialize")
    );
}
