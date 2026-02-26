/**
 * OrgManagerMembers — Sprint 181: Member management for org admins.
 *
 * Add/remove members with role display.
 * Org admins can only add members with "member" role.
 * Cannot remove admin/owner members.
 */
import { useState } from "react";
import { Plus, Trash2, UserCircle } from "lucide-react";
import { useOrgAdminStore } from "@/stores/org-admin-store";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";

const ROLE_LABELS: Record<string, string> = {
  owner: "Chủ sở hữu",
  admin: "Quản trị viên",
  member: "Thành viên",
};

const ROLE_COLORS: Record<string, string> = {
  owner: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  admin: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  member: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

export function OrgManagerMembers({ orgId }: { orgId: string }) {
  const { members, loading, addMember, removeMember } = useOrgAdminStore();
  const [newUserId, setNewUserId] = useState("");
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const handleAddMember = async () => {
    const trimmed = newUserId.trim();
    if (!trimmed || isAdding) return;
    setIsAdding(true);
    try {
      await addMember(orgId, trimmed, "member");
      setNewUserId("");
    } finally {
      setIsAdding(false);
    }
  };

  const handleConfirmRemove = async () => {
    if (removeTarget) {
      await removeMember(orgId, removeTarget);
      setRemoveTarget(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Add member form */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={newUserId}
          onChange={(e) => setNewUserId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAddMember()}
          placeholder="ID người dùng mới"
          maxLength={128}
          className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-text text-sm focus:outline-none focus:ring-1 focus:ring-[var(--accent)] placeholder:text-text-tertiary"
          aria-label="ID người dùng mới"
        />
        <button
          onClick={handleAddMember}
          disabled={!newUserId.trim() || isAdding}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          aria-label="Thêm thành viên"
        >
          <Plus size={14} />
          Thêm
        </button>
      </div>

      {/* Member count */}
      <div className="text-xs text-text-tertiary">
        {members.length} thành viên
      </div>

      {/* Member list */}
      {loading ? (
        <div className="text-center text-text-tertiary py-8 text-sm">
          Đang tải...
        </div>
      ) : members.length === 0 ? (
        <div className="text-center text-text-tertiary py-8 text-sm">
          Chưa có thành viên nào.
        </div>
      ) : (
        <div className="space-y-1">
          {members.map((member) => {
            const isProtected = member.role === "admin" || member.role === "owner";
            return (
              <div
                key={member.user_id}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface-tertiary transition-colors group"
              >
                <UserCircle size={18} className="text-text-tertiary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-text truncate">{member.user_id}</div>
                  {member.joined_at && (
                    <div className="text-[10px] text-text-tertiary">
                      Tham gia: {new Date(member.joined_at).toLocaleDateString("vi-VN")}
                    </div>
                  )}
                </div>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 ${ROLE_COLORS[member.role] || ROLE_COLORS.member}`}>
                  {ROLE_LABELS[member.role] || member.role}
                </span>
                {!isProtected && (
                  <button
                    onClick={() => setRemoveTarget(member.user_id)}
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-all shrink-0"
                    title="Xoá thành viên"
                    aria-label={`Xoá ${member.user_id}`}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm remove dialog */}
      <ConfirmDialog
        open={removeTarget !== null}
        title="Xoá thành viên?"
        message={`Bạn có chắc muốn xoá "${removeTarget}" khỏi tổ chức?`}
        confirmLabel="Xoá"
        cancelLabel="Huỷ"
        variant="danger"
        onConfirm={handleConfirmRemove}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  );
}
