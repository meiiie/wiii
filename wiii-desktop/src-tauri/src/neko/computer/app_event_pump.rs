use super::NekoComputerService;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

const IDLE_RECHECK: Duration = Duration::from_secs(2);
const LONG_POLL_MS: u32 = 10_000;

pub struct AppEventPump {
    stopped: Arc<AtomicBool>,
    wake: Arc<(Mutex<()>, Condvar)>,
    worker: Mutex<Option<JoinHandle<()>>>,
}

impl AppEventPump {
    pub fn start(service: NekoComputerService) -> Result<Self, String> {
        Self::spawn(move |wait_ms, stopped| service.sync_active_app_events(wait_ms, Some(stopped)))
    }

    fn spawn<F>(sync: F) -> Result<Self, String>
    where
        F: Fn(u32, &AtomicBool) -> Result<bool, String> + Send + 'static,
    {
        let stopped = Arc::new(AtomicBool::new(false));
        let wake = Arc::new((Mutex::new(()), Condvar::new()));
        let worker_stopped = stopped.clone();
        let worker_wake = wake.clone();
        let worker = thread::Builder::new()
            .name("wiii-app-event-pump".to_string())
            .spawn(move || {
                while !worker_stopped.load(Ordering::Acquire) {
                    let active = sync(LONG_POLL_MS, &worker_stopped).unwrap_or(false);
                    if active || worker_stopped.load(Ordering::Acquire) {
                        continue;
                    }
                    let (lock, condition) = &*worker_wake;
                    let guard = lock.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
                    drop(condition.wait_timeout(guard, IDLE_RECHECK));
                }
            })
            .map_err(|error| format!("start Wiii app-event pump failed: {error}"))?;
        Ok(Self {
            stopped,
            wake,
            worker: Mutex::new(Some(worker)),
        })
    }

    pub fn shutdown(&self) {
        self.stopped.store(true, Ordering::Release);
        self.wake.1.notify_all();
        let worker = self
            .worker
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .take();
        if let Some(worker) = worker {
            let _ = worker.join();
        }
    }
}

impl Drop for AppEventPump {
    fn drop(&mut self) {
        self.shutdown();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;
    use std::time::Instant;

    #[test]
    fn shutdown_cancels_and_joins_an_active_long_poll() {
        let entered = Arc::new(AtomicUsize::new(0));
        let worker_entered = entered.clone();
        let pump = AppEventPump::spawn(move |_wait_ms, stopped| {
            worker_entered.fetch_add(1, Ordering::SeqCst);
            while !stopped.load(Ordering::Acquire) {
                thread::sleep(Duration::from_millis(2));
            }
            Err("cancelled".to_string())
        })
        .unwrap();
        while entered.load(Ordering::SeqCst) == 0 {
            thread::yield_now();
        }

        let started = Instant::now();
        pump.shutdown();

        assert!(started.elapsed() < Duration::from_millis(250));
        assert!(pump
            .worker
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .is_none());
    }

    #[test]
    fn shutdown_wakes_an_idle_pump_without_waiting_for_the_recheck_interval() {
        let pump = AppEventPump::spawn(|_wait_ms, _stopped| Ok(false)).unwrap();
        thread::sleep(Duration::from_millis(10));

        let started = Instant::now();
        pump.shutdown();

        assert!(started.elapsed() < Duration::from_millis(250));
    }

    #[test]
    fn failed_sync_uses_the_idle_backoff_instead_of_spinning() {
        let calls = Arc::new(AtomicUsize::new(0));
        let worker_calls = calls.clone();
        let pump = AppEventPump::spawn(move |_wait_ms, _stopped| {
            worker_calls.fetch_add(1, Ordering::SeqCst);
            Err("unavailable".to_string())
        })
        .unwrap();
        while calls.load(Ordering::SeqCst) == 0 {
            thread::yield_now();
        }
        thread::sleep(Duration::from_millis(25));

        pump.shutdown();

        assert_eq!(calls.load(Ordering::SeqCst), 1);
    }
}
