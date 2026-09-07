#[allow(dead_code)]
#[path = "../src/neko/bundled_provider.rs"]
mod bundled_provider;
#[allow(dead_code)]
#[path = "../src/neko/provider.rs"]
mod provider;

fn main() {
    let started = std::time::Instant::now();
    let provider_id = std::env::args().nth(1);
    match provider::list_selected(provider_id.as_deref()) {
        Ok(agents) => println!("{}", serde_json::to_string_pretty(&agents).unwrap()),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
    eprintln!("Discovery: {:?}", started.elapsed());
}
