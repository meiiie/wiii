import { LlmRuntimePolicyEditor } from "@/components/runtime/LlmRuntimePolicyEditor";
import { useAdminStore } from "@/stores/admin-store";

export function LlmRuntimeTab() {
  const { showToast } = useAdminStore();

  return (
    <LlmRuntimePolicyEditor
      variant="admin"
      onToast={(message, tone) => showToast(message, tone)}
    />
  );
}
