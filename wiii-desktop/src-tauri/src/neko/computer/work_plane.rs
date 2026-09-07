#[cfg(test)]
use super::model::WorkCapability;
use super::model::{
    WorkPlaneDescribeRequest, WorkPlaneDescriptor, WorkPlaneQueryRequest, WorkPlaneQueryResult,
    WorkPlaneTransactionRequest, WorkPlaneTransactionResult, WorkQueryView,
};

pub(crate) const WORK_PLANE_PROTOCOL: &str = "wiii-work-plane.preview.v1";
const MAX_WORK_INPUT_BYTES: usize = 256 * 1024;

pub(crate) trait WorkPlaneAdapter: Send + Sync {
    fn describe(&self, request: &WorkPlaneDescribeRequest) -> Result<WorkPlaneDescriptor, String>;
    fn query(&self, request: &WorkPlaneQueryRequest) -> Result<WorkPlaneQueryResult, String>;
    fn execute(
        &self,
        request: &WorkPlaneTransactionRequest,
    ) -> Result<WorkPlaneTransactionResult, String>;
}

pub(crate) fn validate_describe(request: &WorkPlaneDescribeRequest) -> Result<(), String> {
    validate_scope(&request.environment_id, &request.project_id)
}

pub(crate) fn validate_query(request: &WorkPlaneQueryRequest) -> Result<(), String> {
    validate_scope(&request.environment_id, &request.project_id)?;
    validate_resource_ref(&request.resource_ref)?;
    if !(1..=200).contains(&request.max_items) {
        return Err("Work Plane maxItems must be between 1 and 200".to_string());
    }
    if request.offset > 10_000_000 {
        return Err("Work Plane offset is too large".to_string());
    }
    if !(1..=64 * 1024).contains(&request.max_bytes) {
        return Err("Work Plane maxBytes must be between 1 and 65536".to_string());
    }
    validate_optional_text("sheet", request.sheet.as_deref(), 200)?;
    validate_optional_text("range", request.range.as_deref(), 100)?;
    match request.view {
        WorkQueryView::Children if request.resource_ref != "work:project" => {
            Err("Work Plane children view requires the Project root".to_string())
        }
        WorkQueryView::Content if request.sheet.is_some() || request.range.is_some() => {
            Err("Work Plane content view does not accept spreadsheet selectors".to_string())
        }
        WorkQueryView::Spreadsheet => Ok(()),
        _ => Ok(()),
    }
}

pub(crate) fn validate_transaction(request: &WorkPlaneTransactionRequest) -> Result<(), String> {
    validate_scope(&request.environment_id, &request.project_id)?;
    validate_identifier("requestId", &request.request_id, 200)?;
    validate_identifier("capabilityId", &request.capability_id, 120)?;
    validate_identifier("capabilityVersion", &request.capability_version, 32)?;
    validate_resource_ref(&request.target_ref)?;
    if !request.if_revision.starts_with("sha256:") || request.if_revision.len() > 96 {
        return Err("Work Plane ifRevision is invalid".to_string());
    }
    if !request.input.is_object() {
        return Err("Work Plane transaction input must be an object".to_string());
    }
    let input_size = serde_json::to_vec(&request.input)
        .map_err(|error| format!("encode Work Plane input failed: {error}"))?
        .len();
    if input_size > MAX_WORK_INPUT_BYTES {
        return Err("Work Plane transaction input exceeds 262144 bytes".to_string());
    }
    Ok(())
}

pub(crate) fn validate_descriptor(descriptor: &WorkPlaneDescriptor) -> Result<(), String> {
    if descriptor.protocol_version != WORK_PLANE_PROTOCOL
        || descriptor.source_authority != "source_application"
        || descriptor.resource_model != "typed_revisioned_resources"
        || descriptor.transaction_model != "optimistic_idempotent"
    {
        return Err("Work Plane provider returned an incompatible descriptor".to_string());
    }
    if descriptor.capabilities.is_empty() || descriptor.capabilities.len() > 32 {
        return Err("Work Plane provider returned an invalid capability catalog".to_string());
    }
    validate_resource_ref(&descriptor.root.resource_ref)?;
    let encoded = serde_json::to_vec(descriptor)
        .map_err(|error| format!("encode Work Plane descriptor failed: {error}"))?;
    if encoded.len() > 64 * 1024 {
        return Err("Work Plane descriptor exceeds 65536 bytes".to_string());
    }
    if contains_provider_detail(&encoded) {
        return Err("Work Plane descriptor exposed provider internals".to_string());
    }
    Ok(())
}

pub(crate) fn validate_query_result(result: &WorkPlaneQueryResult) -> Result<(), String> {
    if result.protocol_version != WORK_PLANE_PROTOCOL || result.items.len() > 200 {
        return Err("Work Plane provider returned an invalid query result".to_string());
    }
    validate_resource_ref(&result.resource.resource_ref)?;
    for item in &result.items {
        validate_resource_ref(&item.resource_ref)?;
    }
    let encoded = serde_json::to_vec(result)
        .map_err(|error| format!("encode Work Plane query result failed: {error}"))?;
    if encoded.len() > 512 * 1024 {
        return Err("Work Plane query result exceeds 524288 bytes".to_string());
    }
    if contains_forbidden_key(
        &serde_json::to_value(result)
            .map_err(|error| format!("encode Work Plane query result failed: {error}"))?,
    ) {
        return Err("Work Plane query exposed provider internals".to_string());
    }
    Ok(())
}

pub(crate) fn validate_transaction_result(
    result: &WorkPlaneTransactionResult,
) -> Result<(), String> {
    if result.protocol_version != WORK_PLANE_PROTOCOL || result.changes.len() > 64 {
        return Err("Work Plane provider returned an invalid transaction result".to_string());
    }
    validate_resource_ref(&result.target_ref)?;
    for change in &result.changes {
        validate_resource_ref(&change.resource_ref)?;
    }
    let encoded = serde_json::to_vec(result)
        .map_err(|error| format!("encode Work Plane transaction result failed: {error}"))?;
    if encoded.len() > 128 * 1024 {
        return Err("Work Plane transaction result exceeds 131072 bytes".to_string());
    }
    if contains_forbidden_key(
        &serde_json::to_value(result)
            .map_err(|error| format!("encode Work Plane transaction result failed: {error}"))?,
    ) {
        return Err("Work Plane transaction exposed provider internals".to_string());
    }
    Ok(())
}

fn validate_scope(environment_id: &str, project_id: &str) -> Result<(), String> {
    validate_identifier("environmentId", environment_id, 128)?;
    validate_identifier("projectId", project_id, 256)
}

fn validate_identifier(label: &str, value: &str, max_length: usize) -> Result<(), String> {
    if value.trim().is_empty() || value.len() > max_length || value.chars().any(char::is_control) {
        return Err(format!("Work Plane {label} is invalid"));
    }
    Ok(())
}

fn validate_optional_text(
    label: &str,
    value: Option<&str>,
    max_length: usize,
) -> Result<(), String> {
    if let Some(value) = value {
        validate_identifier(label, value, max_length)?;
    }
    Ok(())
}

fn validate_resource_ref(value: &str) -> Result<(), String> {
    if value == "work:project"
        || (value.starts_with("work:file:")
            && value.len() <= 512
            && value[10..].chars().all(|character| {
                character.is_ascii_alphanumeric() || matches!(character, '-' | '_')
            }))
    {
        Ok(())
    } else {
        Err("Work Plane resourceRef is invalid".to_string())
    }
}

fn contains_provider_detail(encoded: &[u8]) -> bool {
    let lower = String::from_utf8_lossy(encoded).to_ascii_lowercase();
    [
        "docker",
        "container",
        "attachurl",
        "leaseid",
        "environmentid",
        "/workspace/project",
        "\\\\?\\",
    ]
    .iter()
    .any(|term| lower.contains(term))
}

fn contains_forbidden_key(value: &serde_json::Value) -> bool {
    match value {
        serde_json::Value::Object(map) => map.iter().any(|(key, value)| {
            matches!(
                key.to_ascii_lowercase().as_str(),
                "environmentid"
                    | "attachurl"
                    | "leaseid"
                    | "hostpath"
                    | "containerid"
                    | "containername"
                    | "dockercommand"
            ) || contains_forbidden_key(value)
        }),
        serde_json::Value::Array(values) => values.iter().any(contains_forbidden_key),
        _ => false,
    }
}

#[cfg(test)]
pub(crate) fn base_capabilities(spreadsheet: bool) -> Vec<WorkCapability> {
    let mut capabilities = vec![
        capability(
            "project.file.create",
            &["project.root"],
            serde_json::json!({
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": { "type": "string", "maxLength": 240 },
                    "content": { "type": "string", "maxLength": 131072 }
                },
                "additionalProperties": false
            }),
            true,
            true,
            &["file_hash_readback"],
        ),
        capability(
            "project.file.patch_text",
            &["project.file"],
            serde_json::json!({
                "type": "object",
                "required": ["expectedText", "replacement"],
                "properties": {
                    "expectedText": { "type": "string", "maxLength": 65536 },
                    "replacement": { "type": "string", "maxLength": 131072 }
                },
                "additionalProperties": false
            }),
            true,
            true,
            &["file_hash_readback", "exact_patch_count"],
        ),
        capability(
            "project.file.rename",
            &["project.file", "spreadsheet.workbook"],
            serde_json::json!({
                "type": "object",
                "required": ["destination"],
                "properties": { "destination": { "type": "string", "maxLength": 240 } },
                "additionalProperties": false
            }),
            true,
            true,
            &["source_absent", "destination_hash_readback"],
        ),
    ];
    if spreadsheet {
        capabilities.extend([
            capability(
                "spreadsheet.workbook.create",
                &["project.root"],
                serde_json::json!({
                    "type": "object",
                    "required": ["path", "sheets"],
                    "properties": {
                        "path": { "type": "string", "maxLength": 240 },
                        "sheets": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 16,
                            "items": { "type": "string", "maxLength": 100 }
                        }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["workbook_structure_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.range.set",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "range", "cells"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "range": { "type": "string", "maxLength": 100 },
                        "cells": { "type": "array", "maxItems": 512 }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &[
                    "formula_readback",
                    "recalculated_value",
                    "file_hash_readback",
                ],
            ),
            capability(
                "spreadsheet.range.format",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "range", "format"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "range": { "type": "string", "maxLength": 100 },
                        "format": { "type": "object" }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["format_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.range.merge",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "range", "merged"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "range": { "type": "string", "maxLength": 100 },
                        "merged": { "type": "boolean" }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["merge_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.table.upsert",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "name", "range"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "name": { "type": "string", "maxLength": 100 },
                        "range": { "type": "string", "maxLength": 100 },
                        "hasHeaders": { "type": "boolean" },
                        "autoFilter": { "type": "boolean" }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["table_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.conditional_format.upsert",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "range", "operator", "formula1", "style"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "range": { "type": "string", "maxLength": 100 },
                        "operator": { "enum": ["between", "equal", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "not_equal"] },
                        "formula1": { "type": ["number", "string"] },
                        "formula2": { "type": ["number", "string"] },
                        "style": { "type": "object" },
                        "replace": { "type": "boolean" }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["conditional_format_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.pivot.upsert",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sourceSheet", "sourceRange", "outputSheet", "outputCell", "name", "rows", "columns", "data"],
                    "properties": {
                        "sourceSheet": { "type": "string", "maxLength": 200 },
                        "sourceRange": { "type": "string", "maxLength": 100 },
                        "outputSheet": { "type": "string", "maxLength": 200 },
                        "outputCell": { "type": "string", "maxLength": 100 },
                        "name": { "type": "string", "maxLength": 100 },
                        "rows": { "type": "array", "maxItems": 8 },
                        "columns": { "type": "array", "maxItems": 8 },
                        "data": { "type": "array", "minItems": 1, "maxItems": 16 }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["pivot_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.chart.upsert",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "name", "sourceRange", "anchorRange", "chartType"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "name": { "type": "string", "maxLength": 100 },
                        "sourceRange": { "type": "string", "maxLength": 100 },
                        "anchorRange": { "type": "string", "maxLength": 100 },
                        "chartType": { "enum": ["bar", "column", "line", "pie"] },
                        "title": { "type": "string", "maxLength": 200 },
                        "hasLegend": { "type": "boolean" }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["chart_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.sheet.layout",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["sheet", "printRange", "orientation", "fitWidth", "fitHeight"],
                    "properties": {
                        "sheet": { "type": "string", "maxLength": 200 },
                        "printRange": { "type": "string", "maxLength": 100 },
                        "orientation": { "enum": ["portrait", "landscape"] },
                        "fitWidth": { "type": "integer", "minimum": 1, "maximum": 10 },
                        "fitHeight": { "type": "integer", "minimum": 0, "maximum": 10 },
                        "margin": { "type": "integer", "minimum": 0, "maximum": 5000 }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["page_layout_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.batch",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["operations"],
                    "properties": {
                        "operations": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 64,
                            "items": { "type": "object" }
                        }
                    },
                    "additionalProperties": false
                }),
                true,
                true,
                &["batch_readback", "file_hash_readback"],
            ),
            capability(
                "spreadsheet.export",
                &["spreadsheet.workbook"],
                serde_json::json!({
                    "type": "object",
                    "required": ["format", "destination"],
                    "properties": {
                        "format": { "enum": ["pdf"] },
                        "destination": { "type": "string", "maxLength": 240 }
                    },
                    "additionalProperties": false
                }),
                true,
                false,
                &["export_hash_readback"],
            ),
        ]);
    }
    capabilities
}

#[cfg(test)]
fn capability(
    id: &str,
    resource_types: &[&str],
    input_schema: serde_json::Value,
    mutating: bool,
    reversible: bool,
    evidence: &[&str],
) -> WorkCapability {
    WorkCapability {
        id: id.to_string(),
        version: "1".to_string(),
        resource_types: resource_types
            .iter()
            .map(|value| (*value).to_string())
            .collect(),
        input_schema,
        mutating,
        risk: if reversible {
            "reversible_local_edit"
        } else {
            "local_export"
        }
        .to_string(),
        approval: "project_write_grant".to_string(),
        retry: "idempotency_key_and_revision".to_string(),
        reversible,
        max_input_bytes: MAX_WORK_INPUT_BYTES as u32,
        evidence: evidence.iter().map(|value| (*value).to_string()).collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::neko::computer::model::{
        WorkChange, WorkPlaneTransactionResult, WorkTransactionOutcome,
    };
    use std::collections::HashMap;
    use std::sync::Mutex;

    struct FakeWorkPlaneAdapter {
        revisions: Mutex<HashMap<String, String>>,
    }

    impl FakeWorkPlaneAdapter {
        fn new() -> Self {
            Self {
                revisions: Mutex::new(HashMap::from([
                    (
                        "work:file:YWxwaGE".to_string(),
                        "sha256:alpha-1".to_string(),
                    ),
                    ("work:file:YmV0YQ".to_string(), "sha256:beta-1".to_string()),
                ])),
            }
        }
    }

    impl WorkPlaneAdapter for FakeWorkPlaneAdapter {
        fn describe(
            &self,
            _request: &WorkPlaneDescribeRequest,
        ) -> Result<WorkPlaneDescriptor, String> {
            unreachable!()
        }

        fn query(&self, _request: &WorkPlaneQueryRequest) -> Result<WorkPlaneQueryResult, String> {
            unreachable!()
        }

        fn execute(
            &self,
            request: &WorkPlaneTransactionRequest,
        ) -> Result<WorkPlaneTransactionResult, String> {
            let mut revisions = self.revisions.lock().unwrap();
            let current = revisions.get(&request.target_ref).cloned().unwrap();
            if current != request.if_revision {
                return Ok(WorkPlaneTransactionResult {
                    protocol_version: WORK_PLANE_PROTOCOL.to_string(),
                    outcome: WorkTransactionOutcome::Rejected,
                    code: Some("stale_revision".to_string()),
                    detail: "Refresh the resource before retrying.".to_string(),
                    capability_id: request.capability_id.clone(),
                    target_ref: request.target_ref.clone(),
                    before_revision: current.clone(),
                    after_revision: current,
                    changes: vec![],
                    evidence: vec!["revision_mismatch".to_string()],
                    reversible: true,
                    recovery: Some("query_resource".to_string()),
                });
            }
            let next = format!("sha256:{}-2", request.target_ref);
            revisions.insert(request.target_ref.clone(), next.clone());
            Ok(WorkPlaneTransactionResult {
                protocol_version: WORK_PLANE_PROTOCOL.to_string(),
                outcome: WorkTransactionOutcome::Completed,
                code: None,
                detail: "Source mutation verified.".to_string(),
                capability_id: request.capability_id.clone(),
                target_ref: request.target_ref.clone(),
                before_revision: request.if_revision.clone(),
                after_revision: next.clone(),
                changes: vec![WorkChange {
                    resource_ref: request.target_ref.clone(),
                    kind: "updated".to_string(),
                    before_revision: Some(request.if_revision.clone()),
                    after_revision: Some(next),
                }],
                evidence: vec!["source_readback".to_string()],
                reversible: true,
                recovery: None,
            })
        }
    }

    fn request(target_ref: &str, revision: &str) -> WorkPlaneTransactionRequest {
        WorkPlaneTransactionRequest {
            request_id: format!("op-{target_ref}"),
            environment_id: "computer-test".to_string(),
            project_id: "project-test".to_string(),
            capability_id: "project.file.patch_text".to_string(),
            capability_version: "1".to_string(),
            target_ref: target_ref.to_string(),
            if_revision: revision.to_string(),
            input: serde_json::json!({ "expectedText": "old", "replacement": "new" }),
        }
    }

    #[test]
    fn fake_adapter_refuses_stale_revisions_before_mutation() {
        let adapter = FakeWorkPlaneAdapter::new();
        let result = adapter
            .execute(&request("work:file:YWxwaGE", "sha256:stale"))
            .unwrap();
        assert_eq!(result.outcome, WorkTransactionOutcome::Rejected);
        let current = adapter.revisions.lock().unwrap();
        assert_eq!(current["work:file:YWxwaGE"], "sha256:alpha-1");
    }

    #[test]
    fn fake_adapter_commits_disjoint_resources_without_a_display_lease() {
        let adapter = FakeWorkPlaneAdapter::new();
        let alpha = adapter
            .execute(&request("work:file:YWxwaGE", "sha256:alpha-1"))
            .unwrap();
        let beta = adapter
            .execute(&request("work:file:YmV0YQ", "sha256:beta-1"))
            .unwrap();
        assert_eq!(alpha.outcome, WorkTransactionOutcome::Completed);
        assert_eq!(beta.outcome, WorkTransactionOutcome::Completed);
    }

    #[test]
    fn public_descriptor_rejects_provider_details() {
        let descriptor = WorkPlaneDescriptor {
            protocol_version: WORK_PLANE_PROTOCOL.to_string(),
            source_authority: "source_application".to_string(),
            resource_model: "typed_revisioned_resources".to_string(),
            transaction_model: "optimistic_idempotent".to_string(),
            root: crate::neko::computer::model::WorkResource {
                resource_ref: "work:project".to_string(),
                resource_type: "project.root".to_string(),
                name: "Project".to_string(),
                parent_ref: None,
                revision: "sha256:root".to_string(),
                media_type: None,
                capabilities: vec![],
                source: "project".to_string(),
                metadata: serde_json::json!({ "provider": "docker" }),
            },
            capabilities: base_capabilities(false),
        };
        assert_eq!(
            validate_descriptor(&descriptor).unwrap_err(),
            "Work Plane descriptor exposed provider internals"
        );
    }
}
