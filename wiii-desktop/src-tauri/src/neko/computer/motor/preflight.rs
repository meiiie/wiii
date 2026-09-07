use serde::{Deserialize, Serialize};

const GIB: u64 = 1024 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorPackArtifact {
    pub pack_id: String,
    pub adapter: String,
    pub source_repository: String,
    pub source_revision: String,
    pub source_license: String,
    pub checkpoint_repository: String,
    pub checkpoint_revision: String,
    pub checkpoint_file: String,
    pub checkpoint_sha256: String,
    pub checkpoint_bytes: u64,
    pub checkpoint_license: String,
    pub checkpoint_format: String,
    pub minimum_free_storage_bytes: u64,
    pub reference_system_memory_bytes: u64,
    pub target_hz: u32,
    pub maximum_end_to_end_p95_us: u64,
}

impl MotorPackArtifact {
    pub fn open_p2p_150m() -> Self {
        Self {
            pack_id: "open-p2p-150m-experimental".to_string(),
            adapter: "open-p2p".to_string(),
            source_repository: "https://github.com/elefant-ai/open-p2p".to_string(),
            source_revision: "a329d98cbe62119679a254d71bea6446773541bc".to_string(),
            source_license: "MIT".to_string(),
            checkpoint_repository: "elefantai/open-p2p".to_string(),
            checkpoint_revision: "de18b62bc8f9722bda64497600c38c8f7634d86b".to_string(),
            checkpoint_file: "150M/checkpoint-step=00500000.ckpt".to_string(),
            checkpoint_sha256: "2a3b43121144ca2d9c2b8aa605e313184c98ac5ef6d2c3b530c2d353d886c5bc"
                .to_string(),
            checkpoint_bytes: 2_198_488_343,
            checkpoint_license: "MIT".to_string(),
            checkpoint_format: "pytorch-pickle".to_string(),
            minimum_free_storage_bytes: 12 * GIB,
            reference_system_memory_bytes: 52 * GIB,
            target_hz: 20,
            maximum_end_to_end_p95_us: 50_000,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self != &Self::open_p2p_150m() {
            return Err(
                "Motor pack artifact metadata is not the reviewed pinned build".to_string(),
            );
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MotorHostProbe {
    pub operating_system: String,
    pub cpu: String,
    pub logical_processors: u32,
    pub system_memory_bytes: u64,
    pub free_storage_bytes: u64,
    pub cuda_available: bool,
    pub gpu: Option<String>,
    pub gpu_memory_bytes: Option<u64>,
    pub wsl2_available: bool,
    pub dependency_audit_passed: bool,
    pub measured_hz_milli: Option<u32>,
    pub measured_end_to_end_p95_us: Option<u64>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorPreflightStatus {
    ResearchOnly,
    DownloadEligible,
    EnableEligible,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum MotorFindingLevel {
    Blocker,
    Warning,
    Information,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorPreflightFinding {
    pub code: String,
    pub level: MotorFindingLevel,
    pub detail: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MotorPreflightReport {
    pub schema_version: String,
    pub pack: MotorPackArtifact,
    pub status: MotorPreflightStatus,
    pub fallback: String,
    pub manual_download_required: bool,
    pub findings: Vec<MotorPreflightFinding>,
}

pub fn evaluate_motor_pack(
    pack: MotorPackArtifact,
    probe: MotorHostProbe,
) -> Result<MotorPreflightReport, String> {
    pack.validate()?;
    validate_probe(&probe)?;
    let mut findings = vec![MotorPreflightFinding {
        code: "pickle_checkpoint".to_string(),
        level: MotorFindingLevel::Warning,
        detail: "Checkpoint loading must remain isolated and hash-verified because the reviewed artifact uses PyTorch pickle".to_string(),
    }];
    if probe.free_storage_bytes < pack.minimum_free_storage_bytes {
        findings.push(blocker(
            "storage_below_gate",
            "Free storage is below the pack download, runtime and rollback budget",
        ));
    }
    if !probe.cuda_available {
        findings.push(blocker(
            "cuda_unavailable",
            "The reviewed Open P2P runtime requires CUDA inference",
        ));
    }
    if probe
        .operating_system
        .to_ascii_lowercase()
        .contains("windows")
        && !probe.wsl2_available
    {
        findings.push(blocker(
            "wsl2_unavailable",
            "The reviewed Windows inference route requires WSL2",
        ));
    }
    if !probe.dependency_audit_passed {
        findings.push(blocker(
            "dependency_audit_missing",
            "Runtime dependencies have not passed license, provenance and vulnerability review",
        ));
    }
    if probe.system_memory_bytes < pack.reference_system_memory_bytes {
        findings.push(MotorPreflightFinding {
            code: "below_reference_memory".to_string(),
            level: MotorFindingLevel::Warning,
            detail: "System memory is below the upstream Windows WSL reference recommendation"
                .to_string(),
        });
    }

    let resources_blocked = findings
        .iter()
        .any(|finding| finding.level == MotorFindingLevel::Blocker);
    let measured = match (probe.measured_hz_milli, probe.measured_end_to_end_p95_us) {
        (Some(hz), Some(p95)) => Some((hz, p95)),
        (None, None) => None,
        _ => return Err("Motor host probe contains a partial latency measurement".to_string()),
    };
    let status = if resources_blocked {
        MotorPreflightStatus::ResearchOnly
    } else if let Some((hz_milli, p95_us)) = measured {
        if hz_milli >= pack.target_hz * 1000 && p95_us < pack.maximum_end_to_end_p95_us {
            MotorPreflightStatus::EnableEligible
        } else {
            findings.push(blocker(
                "latency_gate_failed",
                "Measured policy throughput or end-to-end p95 missed the realtime gate",
            ));
            MotorPreflightStatus::ResearchOnly
        }
    } else {
        findings.push(MotorPreflightFinding {
            code: "latency_measurement_required".to_string(),
            level: MotorFindingLevel::Information,
            detail: "The artifact may be downloaded only after explicit approval; Motor remains disabled until an on-device latency run passes".to_string(),
        });
        MotorPreflightStatus::DownloadEligible
    };
    Ok(MotorPreflightReport {
        schema_version: "wiii-motor-preflight.v1".to_string(),
        pack,
        status,
        fallback: "semantic".to_string(),
        manual_download_required: true,
        findings,
    })
}

fn validate_probe(probe: &MotorHostProbe) -> Result<(), String> {
    if probe.operating_system.trim().is_empty()
        || probe.operating_system.len() > 128
        || probe.cpu.trim().is_empty()
        || probe.cpu.len() > 192
    {
        return Err("Motor host identity is missing or oversized".to_string());
    }
    if probe.logical_processors == 0
        || probe.system_memory_bytes == 0
        || probe.free_storage_bytes == 0
    {
        return Err("Motor host capacity values must be positive".to_string());
    }
    if probe.gpu.as_ref().is_some_and(|value| value.len() > 192) {
        return Err("Motor GPU identity is oversized".to_string());
    }
    Ok(())
}

fn blocker(code: &str, detail: &str) -> MotorPreflightFinding {
    MotorPreflightFinding {
        code: code.to_string(),
        level: MotorFindingLevel::Blocker,
        detail: detail.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn probe() -> MotorHostProbe {
        MotorHostProbe {
            operating_system: "Windows 11".to_string(),
            cpu: "Test CPU".to_string(),
            logical_processors: 16,
            system_memory_bytes: 64 * GIB,
            free_storage_bytes: 100 * GIB,
            cuda_available: true,
            gpu: Some("Test CUDA GPU".to_string()),
            gpu_memory_bytes: Some(24 * GIB),
            wsl2_available: true,
            dependency_audit_passed: true,
            measured_hz_milli: None,
            measured_end_to_end_p95_us: None,
        }
    }

    #[test]
    fn exact_artifact_is_hash_size_and_license_pinned() {
        let pack = MotorPackArtifact::open_p2p_150m();
        pack.validate().unwrap();
        assert_eq!(pack.checkpoint_bytes, 2_198_488_343);
        assert_eq!(pack.checkpoint_sha256.len(), 64);
        assert_eq!(pack.checkpoint_license, "MIT");
    }

    #[test]
    fn download_never_implies_motor_enablement() {
        let report = evaluate_motor_pack(MotorPackArtifact::open_p2p_150m(), probe()).unwrap();
        assert_eq!(report.status, MotorPreflightStatus::DownloadEligible);
        assert_eq!(report.fallback, "semantic");
        assert!(report.manual_download_required);
    }

    #[test]
    fn measured_latency_and_frequency_are_both_required() {
        let mut host = probe();
        host.measured_hz_milli = Some(20_000);
        assert!(
            evaluate_motor_pack(MotorPackArtifact::open_p2p_150m(), host)
                .unwrap_err()
                .contains("partial")
        );

        let mut host = probe();
        host.measured_hz_milli = Some(20_000);
        host.measured_end_to_end_p95_us = Some(49_999);
        assert_eq!(
            evaluate_motor_pack(MotorPackArtifact::open_p2p_150m(), host)
                .unwrap()
                .status,
            MotorPreflightStatus::EnableEligible
        );
    }

    #[test]
    fn resource_or_dependency_failure_keeps_semantic_fallback() {
        let mut host = probe();
        host.system_memory_bytes = 16 * GIB;
        host.free_storage_bytes = 4 * GIB;
        host.dependency_audit_passed = false;
        let report = evaluate_motor_pack(MotorPackArtifact::open_p2p_150m(), host).unwrap();
        assert_eq!(report.status, MotorPreflightStatus::ResearchOnly);
        assert_eq!(report.fallback, "semantic");
        assert!(report
            .findings
            .iter()
            .any(|finding| finding.code == "dependency_audit_missing"));
    }
}
