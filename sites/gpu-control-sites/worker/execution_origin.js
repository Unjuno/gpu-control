export function executionOrigin(row) {
  if (typeof row.lease_id === "string" && /^sb-[A-Za-z0-9]+$/.test(row.lease_id)) return "modal_sandbox";
  if (typeof row.cleanup_receipt_json === "string") {
    try {
      const receipt = JSON.parse(row.cleanup_receipt_json);
      if (receipt && typeof receipt === "object" && !Array.isArray(receipt) &&
          receipt.absent === true && receipt.run_id === row.id &&
          receipt.container_name === `gpu-control-${row.id}` &&
          typeof receipt.container_id === "string" && /^[0-9a-f]{64}$/.test(receipt.container_id) &&
          receipt.image_digest === row.image_digest &&
          typeof receipt.lease_id === "string" && /^[0-9a-f]{32}$/.test(receipt.lease_id)) {
        return "retired_local_runner";
      }
    } catch {}
  }
  return "unknown";
}
