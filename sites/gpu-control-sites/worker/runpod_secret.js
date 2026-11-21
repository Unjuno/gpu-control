const HEX_32_RE = /^[0-9a-f]{32}$/;
const HEX_64_RE = /^[0-9a-f]{64}$/;

export class RunpodSecretError extends Error {
  constructor(code) {
    super(code);
    this.name = "RunpodSecretError";
    this.code = code;
  }
}

function fromBase64(value, code, expectedLength = null) {
  if (typeof value !== "string" || value.length < 4 || value.length > 512 ||
      !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) {
    throw new RunpodSecretError(code);
  }
  const bytes = Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
  if (expectedLength !== null && bytes.length !== expectedLength) throw new RunpodSecretError(code);
  return bytes;
}

function toBase64(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

async function encryptionKey(keyB64, usage) {
  const bytes = fromBase64(keyB64, "RUNPOD_STATE_ENCRYPTION_KEY_INVALID", 32);
  try {
    return await crypto.subtle.importKey("raw", bytes, { name: "AES-GCM" }, false, [usage]);
  } finally {
    bytes.fill(0);
  }
}

function aad({ runId, ownerId, planFingerprint, keyId }) {
  if (!/^[0-9a-f]{32}$/.test(runId) || typeof ownerId !== "string" || ownerId.length < 1 || ownerId.length > 256 ||
      !HEX_64_RE.test(planFingerprint) || !HEX_32_RE.test(keyId)) {
    throw new RunpodSecretError("RUNPOD_SECRET_BINDING_INVALID");
  }
  return new TextEncoder().encode(`gpu-control/runpod-completion-key/v1\0${runId}\0${ownerId}\0${planFingerprint}\0${keyId}`);
}

export async function sealCompletionKey({ stateEncryptionKeyB64, completionKeyBytes, binding }) {
  if (!(completionKeyBytes instanceof Uint8Array) || completionKeyBytes.length !== 32) {
    throw new RunpodSecretError("RUNPOD_COMPLETION_KEY_INVALID");
  }
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await encryptionKey(stateEncryptionKeyB64, "encrypt");
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: aad(binding), tagLength: 128 }, key, completionKeyBytes,
  ));
  return { ivB64: toBase64(iv), ciphertextB64: toBase64(ciphertext) };
}

export async function openCompletionKey({ stateEncryptionKeyB64, ivB64, ciphertextB64, binding }) {
  const iv = fromBase64(ivB64, "RUNPOD_SECRET_IV_INVALID", 12);
  const ciphertext = fromBase64(ciphertextB64, "RUNPOD_SECRET_CIPHERTEXT_INVALID");
  if (ciphertext.length !== 48) throw new RunpodSecretError("RUNPOD_SECRET_CIPHERTEXT_INVALID");
  const key = await encryptionKey(stateEncryptionKeyB64, "decrypt");
  try {
    const plaintext = new Uint8Array(await crypto.subtle.decrypt(
      { name: "AES-GCM", iv, additionalData: aad(binding), tagLength: 128 }, key, ciphertext,
    ));
    if (plaintext.length !== 32) throw new RunpodSecretError("RUNPOD_COMPLETION_KEY_INVALID");
    return plaintext;
  } catch (error) {
    if (error instanceof RunpodSecretError) throw error;
    throw new RunpodSecretError("RUNPOD_SECRET_AUTHENTICATION_FAILED");
  } finally {
    iv.fill(0);
    ciphertext.fill(0);
  }
}
