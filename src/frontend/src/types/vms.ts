export type VmStatus = "pending" | "approved" | "rejected" | "revoked";

export type VmRecord = {
  vm_id: string;
  hostname: string;
  fingerprint?: string;
  status: VmStatus;
  registered_at?: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  revoked_at?: string | null;
  last_ship_at?: string | null;
  s3_prefix?: string | null;
  metadata?: Record<string, unknown>;
};

export type VmsListResponse = {
  vms: VmRecord[];
  count: number;
};

export type VmRegisterResponse = {
  vm_id: string;
  status: VmStatus;
  api_token: string;
  message?: string;
};

export type VmActionResponse = {
  ok: boolean;
  vm: VmRecord;
  s3_marker?: string;
};
