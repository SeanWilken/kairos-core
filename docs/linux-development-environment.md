# Zorin OS AI Development Workstation

This guide targets a Zorin OS workstation with an Intel Core i9-14900, an
NVIDIA RTX 2080, and a dedicated 1 TB NVMe for containers, models, datasets,
and experiments. It is designed for MyAI suite development, local inference,
Hugging Face evaluation, and an incremental path toward LoRA/QLoRA training.

Zorin is Ubuntu-based. Always identify the underlying Ubuntu release before
adding NVIDIA, Podman, or CUDA repositories:

```bash
cat /etc/os-release
lsb_release -a
uname -r
```

Use repository instructions for that Ubuntu base, not only the visible Zorin
version.

This procedure requires an Ubuntu 24.04 base and Podman 4.9 or newer. Zorin 17
is based on Ubuntu 22.04 and its default Podman lacks features used here,
including current CDI and Quadlet support. Upgrade the operating system or
install a supported newer Podman before continuing; mixing Jammy packages with
repositories for another Ubuntu release is not supported.

## Key Decisions

- Mount the dedicated NVMe at `/srv/ai`, not `/srv`. Other system services may
  legitimately use `/srv` later.
- Native Linux Podman does not use a Podman VM. Relocate its rootless
  `graphroot`; there is no VM disk to move.
- Keep replaceable Podman layers separate from models, datasets, checkpoints,
  and databases.
- Use the host NVIDIA driver plus NVIDIA CDI for rootless Podman. Do not install
  a full host CUDA toolkit unless compiling CUDA software on the host.
- Start with Ollama for daily use and `llama.cpp` for controlled GGUF testing.
- Use Transformers, PEFT, TRL, and Accelerate for model research and training.
- Treat `stable` model and container promotion as an evaluated release action,
  not as an automatic consequence of downloading or training a model.

## Hardware Expectations

The RTX 2080 is a Turing GPU with 8 GB of VRAM. The desktop compositor reduces
the memory available to inference. It is a good development card for quantized
3B-4B models and constrained 7B-8B testing, but it is not a comfortable 8B+
training card.

Recommended system memory:

- 64 GB RAM: practical minimum for this workstation.
- 128 GB RAM: preferred for CPU offload, data preparation, multiple containers,
  and model conversion.

Before model work, update the motherboard UEFI and Intel microcode and use the
vendor's current Intel-default power profile. The i9-14900 is part of the
13th/14th-generation desktop family affected by historical instability from
older firmware and unrestricted power defaults.

## 1. Prepare the Secondary NVMe

### Filesystem

Use ext4 unless XFS project quotas are a specific requirement. Do not use NTFS,
exFAT, NFS, or a desktop auto-mount path for Podman graph storage.

Identify the correct device carefully:

```bash
lsblk -o NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINTS
sudo nvme list
```

The following destructive commands are examples only. Replace the device name
after confirming it is the new secondary drive:

```bash
sudo parted /dev/nvme1n1 --script mklabel gpt
sudo parted /dev/nvme1n1 --script mkpart primary ext4 0% 100%
sudo mkfs.ext4 -L myai-data /dev/nvme1n1p1
```

Get its UUID:

```bash
sudo blkid /dev/nvme1n1p1
```

Create the mount and add an `/etc/fstab` entry using the UUID:

```bash
sudo mkdir -p /srv/ai
sudoedit /etc/fstab
```

<!-- markdownlint-disable MD013 -->

```fstab
UUID=replace-with-actual-uuid /srv/ai ext4 defaults,noatime,x-systemd.device-timeout=10s 0 2
```

<!-- markdownlint-enable MD013 -->

Do not add `nofail`. A silent mount failure could cause Podman and model tools
to fill the operating-system drive instead.

Validate before rebooting:

```bash
sudo mount -a
findmnt /srv/ai
df -h /srv/ai
```

Enable periodic trim and health tooling:

```bash
sudo systemctl enable --now fstrim.timer
sudo apt update
sudo apt install -y nvme-cli smartmontools
sudo nvme smart-log /dev/nvme1
```

Keep at least 15% of the NVMe free for image extraction, checkpoints, temporary
model conversion, and SSD garbage collection.

## 2. Storage Layout

Use explicit directories rather than placing durable data inside container
writable layers:

```text
/srv/ai/
  podman/storage/           Replaceable rootless Podman graph storage
  containers/               Persistent application and database data
  models/gguf/              llama.cpp-compatible quantized models
  models/ollama/            Ollama-managed manifests and blobs
  huggingface/hub/          Original model/tokenizer snapshots
  huggingface/datasets/     Hugging Face datasets cache
  datasets/raw/             Immutable source datasets
  datasets/processed/       Versioned prepared datasets
  checkpoints/adapters/     LoRA/QLoRA adapters
  checkpoints/merged/       Optional merged model outputs
  experiments/mlflow/       Local experiment metadata and artifacts
  experiments/evaluations/  Evaluation results
  dvc-cache/                Local DVC cache
  stacks/                   Compose and Quadlet definitions
  scratch/                  Disposable conversion and training files
```

Create and secure the layout:

```bash
sudo mkdir -p \
  /srv/ai/podman/storage \
  /srv/ai/containers \
  /srv/ai/models/gguf \
  /srv/ai/models/ollama \
  /srv/ai/huggingface/hub \
  /srv/ai/huggingface/datasets \
  /srv/ai/datasets/raw \
  /srv/ai/datasets/processed \
  /srv/ai/checkpoints/adapters \
  /srv/ai/checkpoints/merged \
  /srv/ai/experiments/mlflow \
  /srv/ai/experiments/evaluations \
  /srv/ai/dvc-cache \
  /srv/ai/stacks \
  /srv/ai/scratch

sudo chown -R "$USER:$USER" /srv/ai
sudo chmod 711 /srv/ai /srv/ai/models
chmod 700 \
  /srv/ai/podman \
  /srv/ai/containers \
  /srv/ai/huggingface \
  /srv/ai/datasets \
  /srv/ai/checkpoints \
  /srv/ai/experiments \
  /srv/ai/dvc-cache \
  /srv/ai/stacks \
  /srv/ai/scratch
```

The execute-only access on `/srv/ai` and `/srv/ai/models` lets dedicated
service accounts traverse to explicitly granted directories without allowing
them to list the workstation owner's data.

A practical 1 TB budget is:

| Category | Initial budget |
| --- | ---: |
| Podman layers and build cache | 150 GB |
| Downloaded models | 350 GB |
| Datasets and Hugging Face cache | 150 GB |
| Checkpoints and experiment artifacts | 150 GB |
| Databases and persistent containers | 50 GB |
| Required free/scratch capacity | 150 GB |

These are monitoring targets, not partitions. Directories are easier to resize
as the workload becomes clear.

## 3. Install Rootless Podman

Install Podman from repositories for the detected Ubuntu base. This guide
requires Podman 4.9 or newer.

```bash
sudo apt update
sudo apt install -y \
  podman \
  podman-compose \
  uidmap \
  fuse-overlayfs \
  slirp4netns \
  passt \
  jq \
  curl

podman version
podman compose version
```

Stop if either command is unavailable or Podman is older than 4.9. The
`podman compose` command also requires an installed Compose provider such as
`podman-compose`.

Verify subordinate user mappings:

```bash
grep "^$USER:" /etc/subuid
grep "^$USER:" /etc/subgid
sort -t: -k2n /etc/subuid
sort -t: -k2n /etc/subgid
```

If the user's mappings are missing, allocate a unique, non-overlapping range
of at least 65,536 IDs using the distribution's account-management tooling.
Do not copy a fixed range from another machine or assign a range already owned
by another account. If Podman was initialized before changing the mappings,
run `podman system migrate` afterward.

Log out and back in after changing those mappings. Do not alternate between
`podman` and `sudo podman`; rootless and rootful stores are separate.

### Move Podman storage

Configure this before pulling images:

```bash
mkdir -p ~/.config/containers
nano ~/.config/containers/storage.conf
```

```toml
[storage]
driver = "overlay"
graphroot = "/srv/ai/podman/storage"

[storage.options.overlay]
mountopt = "nodev"
```

Do not hardcode `runroot`; Podman should keep transient runtime state under
`/run/user/$UID`. On a current kernel, first try native rootless OverlayFS. Add
the following only if `podman info` or an actual container run shows that
`fuse-overlayfs` is required:

```toml
mount_program = "/usr/bin/fuse-overlayfs"
```

Verify:

```bash
podman info --format json | jq '{
  rootless: .host.security.rootless,
  graphDriver: .store.graphDriverName,
  graphRoot: .store.graphRoot,
  runRoot: .store.runRoot
}'

podman run --rm docker.io/library/alpine:latest uname -a
```

Expected graph root:

```text
/srv/ai/podman/storage
```

Changing `graphroot` does not migrate an existing store. For a fresh machine,
configure it first. For an established machine, export durable data and
recreate containers rather than moving graph internals unless preserving
xattrs, hard links, ownership, and user-namespace mappings is well understood.

## 4. NVIDIA Driver and Container GPU Access

### Host driver

Use the Ubuntu/Zorin packaged driver or NVIDIA's APT repository, not NVIDIA's
`.run` installer:

```bash
sudo ubuntu-drivers devices
sudo ubuntu-drivers autoinstall
sudo reboot
```

After reboot:

```bash
nvidia-smi
lsmod | grep nvidia
```

If Secure Boot is enabled, complete the MOK enrollment process for the NVIDIA
kernel module. A package can appear installed while Secure Boot still prevents
the module from loading.

The host generally needs only the driver. Runtimes and containers should carry
their tested CUDA user-space libraries. Install a versioned host CUDA toolkit
only when compiling CUDA code locally. The `CUDA Version` displayed by
`nvidia-smi` is the maximum driver-supported CUDA API, not proof that the host
toolkit is installed.

### NVIDIA Container Toolkit and CDI

Follow NVIDIA's current Debian/Ubuntu repository instructions, then install:

```bash
sudo apt install -y nvidia-container-toolkit
```

NVIDIA Container Toolkit 1.18 or newer generates CDI definitions through
`nvidia-cdi-refresh`. Verify the path unit, generated specification, and last
refresh result; the oneshot service can correctly be inactive after it exits:

```bash
nvidia-ctk cdi list
systemctl status nvidia-cdi-refresh.path --no-pager
systemctl show nvidia-cdi-refresh.service -p Result
sudo test -s /var/run/cdi/nvidia.yaml
```

Test rootless Podman GPU access:

```bash
podman run --rm \
  --device nvidia.com/gpu=all \
  docker.io/nvidia/cuda:12.8.1-base-ubuntu24.04 \
  nvidia-smi
```

Use CDI rather than mixing it with the legacy NVIDIA OCI hook or
`NVIDIA_VISIBLE_DEVICES`. Do not use `--privileged` for normal GPU workloads.
Remove or disable an old NVIDIA OCI hook before using CDI. Confirm the login
user can access `/dev/nvidia*`; if access comes only from a supplementary
group, add `--group-add keep-groups` to the rootless Podman test.

## 5. Recommended Local Inference Stack

Use separate tools for separate jobs:

| Tool | Best use |
| --- | --- |
| Ollama | Daily model management and a simple local API |
| llama.cpp | GGUF benchmarking and exact GPU/context/KV-cache control |
| LM Studio | Desktop model discovery and interactive parameter testing |
| Open WebUI | Browser UI and provider aggregation; not an inference engine |
| Transformers | Original Hugging Face checkpoints, evaluation, and training |
| vLLM | Future high-throughput serving on a larger GPU |
| LocalAI | Optional multi-backend OpenAI-compatible abstraction |

Do not run all inference engines simultaneously. Start with Ollama plus
`llama.cpp`; add LM Studio only when its desktop workflow is useful.

### Ollama

Install Ollama using its current official Linux instructions. Configure model
storage in a systemd override rather than moving files with ad hoc symlinks:

The packaged service normally runs as the `ollama` user, so grant that account
ownership of only its model directory after installation:

```bash
sudo chown -R ollama:ollama /srv/ai/models/ollama
sudo chmod 750 /srv/ai/models/ollama
```

```bash
sudo systemctl edit ollama.service
```

```ini
[Service]
Environment="OLLAMA_MODELS=/srv/ai/models/ollama"
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
ollama ps
curl http://127.0.0.1:11434/api/tags
```

Start with:

```bash
ollama run qwen3:4b
```

Use 4K context first. Raise it to 8K only after observing VRAM with
`nvidia-smi` and confirming that the model remains fully GPU-resident.

### llama.cpp

Use `llama.cpp` as the repeatable baseline for GGUF models. Build a reviewed
revision with CUDA support rather than relying on an unknown host binary:

```bash
git clone https://github.com/ggml-org/llama.cpp.git ~/src/llama.cpp
cd ~/src/llama.cpp
: "${LLAMA_CPP_REVISION:?Set LLAMA_CPP_REVISION to a reviewed full commit SHA}"
git checkout "$LLAMA_CPP_REVISION"
cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j"$(nproc)"
./build/bin/llama-server --list-devices
```

It exposes explicit GPU-layer, context, batch, and KV-cache controls and
includes an OpenAI-compatible server.

For the RTX 2080, begin with a Qwen3-4B Q5_K_M or Q6_K GGUF:

```bash
~/src/llama.cpp/build/bin/llama-server \
  --model /srv/ai/models/gguf/Qwen3-4B-Q5_K_M.gguf \
  --host 127.0.0.1 \
  --port 8088 \
  --ctx-size 4096 \
  --n-gpu-layers 999 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0
```

Test:

```bash
curl http://127.0.0.1:8088/v1/models | jq
```

### Connect MyAI Core to a local model

Ollama and `llama-server` expose OpenAI-compatible endpoints. Current Core
provider adapters use `LLM_ENDPOINT` for that base URL and require a non-empty
API-key value to leave simulated mode.

For Core running natively:

```dotenv
LLM_PROVIDER=openai
LLM_ENDPOINT=http://127.0.0.1:11434/v1
LLM_MODEL=qwen3:4b
LLM_FAST_MODEL=qwen3:4b
OPENAI_API_KEY=ollama-local
```

For Core in rootless Podman while Ollama runs on the host:

```dotenv
LLM_PROVIDER=openai
LLM_ENDPOINT=http://host.containers.internal:11434/v1
LLM_MODEL=qwen3:4b
LLM_FAST_MODEL=qwen3:4b
OPENAI_API_KEY=ollama-local
```

The loopback-bound host service requires explicit rootless loopback forwarding
with the `slirp4netns` backend. Test it before deploying Core:

```bash
podman run --rm \
  --network=slirp4netns:allow_host_loopback=true \
  docker.io/library/alpine:3.21 \
  wget -qO- http://host.containers.internal:11434/api/tags
```

Apply the same network mode to containers that use this endpoint. Do not work
around a failed test by exposing unauthenticated Ollama on `0.0.0.0`.

The placeholder key is local-only and is not a substitute for a real provider
key when `LLM_ENDPOINT` points to a hosted service.

### Open WebUI

Run Open WebUI under rootless Podman while Ollama remains native:

```bash
mkdir -p /srv/ai/containers/open-webui
install -d -m 0700 ~/.config/myai
install -m 0600 /dev/null ~/.config/myai/open-webui.env
WEBUI_SECRET_KEY="$(openssl rand -hex 32)"
printf 'WEBUI_SECRET_KEY=%s\n' "$WEBUI_SECRET_KEY" > ~/.config/myai/open-webui.env
unset WEBUI_SECRET_KEY

: "${OPEN_WEBUI_IMAGE:?Set OPEN_WEBUI_IMAGE to a reviewed version or digest}"

podman run -d \
  --name open-webui \
  --restart=unless-stopped \
  --network=slirp4netns:allow_host_loopback=true \
  -p 127.0.0.1:3000:8080 \
  --env-file ~/.config/myai/open-webui.env \
  -e OLLAMA_BASE_URL=http://host.containers.internal:11434 \
  -v /srv/ai/containers/open-webui:/app/backend/data \
  "$OPEN_WEBUI_IMAGE"
```

Pin a reviewed image version or digest. Do not use `main` as a deployment
contract. The first account registered in a new Open WebUI installation becomes
its administrator, so create it before allowing any other user to connect.

## 6. Model Selection for the RTX 2080

Practical starting points:

| Model | Expected RTX 2080 use |
| --- | --- |
| Qwen3 0.6B or 1.7B | Fast experiments and training-pipeline validation |
| Qwen3 4B Q5_K_M/Q6_K | Recommended general local model |
| Qwen3 8B Q4_K_M | Near the VRAM limit; use 4K context initially |
| Qwen2.5-Coder 3B/7B quantized | Useful coding comparison |
| Phi-4 Mini Instruct | Useful compact instruction-model comparison |
| Gemma 3 4B quantized | Useful quality and tool-use comparison |
| 14B Q4 | Requires substantial CPU/RAM offload; not a daily target |

Do not choose only by parameter count. Record:

- Model revision and license.
- Quantization format and size.
- Context length and KV-cache format.
- Tokens per second and first-token latency.
- Peak VRAM and system RAM.
- Tool-calling/JSON reliability.
- Retrieval grounding and hallucination rate.
- Performance on MyAI-specific evaluation cases.

Avoid using unified-memory overflow as the normal operating mode. Explicit CPU
layer offload is slower but more predictable.

## 7. Hugging Face Model Testing

Set cache locations in `~/.profile`:

```bash
export HF_HOME=/srv/ai/huggingface
export HF_HUB_CACHE=/srv/ai/huggingface/hub
export HF_DATASETS_CACHE=/srv/ai/huggingface/datasets
```

Use the current `hf` CLI and authenticate through its credential store:

```bash
hf auth login
hf auth whoami
: "${HF_MODEL_REVISION:?Set HF_MODEL_REVISION to a reviewed full commit SHA}"
hf download Qwen/Qwen3-4B-GGUF \
  Qwen3-4B-Q5_K_M.gguf \
  --revision "$HF_MODEL_REVISION" \
  --dry-run
```

Use isolated Python environments. `uv` is a good default:

```bash
mkdir -p ~/venvs
uv venv ~/venvs/hf-inference --python 3.12
source ~/venvs/hf-inference/bin/activate
```

Install PyTorch first using the exact command from its compatibility matrix for
the selected release and CUDA runtime. Then install the inference and training
packages and capture a lock in a project `pyproject.toml`/`uv.lock` before a
reproducible run:

```bash
uv pip install \
  transformers \
  accelerate \
  bitsandbytes \
  safetensors \
  huggingface-hub \
  peft \
  trl \
  datasets \
  mlflow \
  dvc

python - <<'PY'
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
PY
```

Install PyTorch using the wheel index matching the installed NVIDIA driver and
the current PyTorch compatibility matrix. Do not blindly use an arbitrary CUDA
wheel copied from another machine.

Recommended applications and utilities:

- LM Studio: interactive GGUF discovery and parameter testing.
- Open WebUI: conversational and RAG testing across local endpoints.
- llama.cpp: repeatable GGUF performance measurements.
- Transformers: original checkpoint behavior and quantization tests.
- `lm-evaluation-harness` or LightEval: benchmark suites.
- Promptfoo: API-level regression suites for prompts, structured output, and
  tool calling.
- Ragas or DeepEval: retrieval/evidence evaluation after RAG integration.
- JupyterLab: exploratory notebooks, not the source of record for production
  training pipelines.

Security practices:

- Pin model downloads to a full Hugging Face commit revision.
- Prefer `safetensors` over pickle-based formats.
- Avoid `trust_remote_code=True` unless the repository code was reviewed and
  the revision is pinned.
- Review licenses and dataset terms before suite integration or redistribution.

## 8. Training Progression

Train from original Hugging Face `safetensors` checkpoints, not GGUF. Convert a
merged result to GGUF only after training and evaluation.

### Recommended toolchain

- Transformers: model and tokenizer foundation.
- PEFT: LoRA and QLoRA adapters.
- TRL: supervised fine-tuning first; preference optimization later.
- Accelerate: device and mixed-precision configuration.
- bitsandbytes: NF4/FP4 loading and memory-efficient optimizers.
- Unsloth: optional optimization after a plain PEFT/TRL baseline works.
- MLflow: local run metadata, metrics, and artifacts.
- DVC: dataset and checkpoint lineage.

Axolotl is useful for configuration-driven training, but its most optimized
paths increasingly assume Ampere-or-newer hardware. It should not be the first
baseline on an RTX 2080.

### RTX 2080 settings

Use:

- FP16 compute, not BF16; Turing lacks native BF16 acceleration.
- QLoRA with a 4-bit NF4 base model and double quantization.
- `bnb_4bit_compute_dtype=torch.float16` and
  `bnb_4bit_quant_type="nf4"` with `bnb_4bit_use_double_quant=True`.
- Batch size 1 plus gradient accumulation.
- Gradient checkpointing.
- Sequence length 512 initially, then 1024 after measuring memory.
- LoRA rank 8 or 16 initially.
- An 8-bit or paged optimizer.
- Adapter-only checkpoints.
- Explicit LoRA target modules verified against the selected model architecture;
  4-bit base weights remain frozen while adapter parameters are trained.
- A separate evaluation process when training memory is tight.

Progression:

1. Fine-tune Qwen3 0.6B or 1.7B on a small synthetic/test dataset.
2. Reproduce the run with fixed seeds and tracked versions.
3. Establish held-out quality and regression tests.
4. Move to a 3B-4B QLoRA run.
5. Attempt 7B-8B only after the pipeline is stable and with short sequences.
6. Use a 24 GB or larger GPU for routine 8B training and 14B experimentation.

Do not use `device_map="auto"` for training; it is primarily an inference
placement mechanism.

### Experiment tracking

Start MLflow locally:

```bash
uv tool install mlflow
mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri sqlite:////srv/ai/experiments/mlflow/mlflow.db \
  --artifacts-destination /srv/ai/experiments/mlflow/artifacts
```

Set `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` in each training environment
that should report to this server.

Use DVC for datasets and large artifacts, but configure a true remote on
off-host storage, removable media stored separately, a backed-up NAS, or
versioned object storage. Another internal disk is a useful replica, not a
backup, because it shares the workstation's failure domain. In each DVC
repository, run `dvc cache dir /srv/ai/dvc-cache`, configure a remote, and
verify both `dvc push` and `dvc pull`.

Record for every run:

- Git commit.
- Model and tokenizer revision.
- Dataset DVC hash.
- Chat template and prompt format.
- Random seed.
- Driver, CUDA runtime, PyTorch, Transformers, PEFT, TRL, and bitsandbytes
  versions.
- Quantization, adapter, optimizer, batch, and sequence configuration.
- GPU model, VRAM, peak memory, runtime, and evaluation results.

## 9. GPU Upgrade Guidance

For this workload, prioritize VRAM and current software support over a used
card's original Tesla branding.

Preferred practical upgrades:

- RTX 3090 24 GB: often the best used-workstation value if power and cooling
  are acceptable.
- RTX 4090 24 GB: substantially faster, but still limited to 24 GB.
- RTX 5090 32 GB: stronger local training capacity if budget and platform
  support allow it.
- RTX A5000/A5500 24 GB: lower-power professional options.
- RTX A6000 48 GB: strong single-workstation capacity at a higher cost.
- NVIDIA A10 24 GB: viable data-center card with proper server airflow.

Be cautious with used Tesla P40/P100 and V100 cards:

- Passive cooling may require high-pressure server airflow.
- Pascal/Volta support is being removed from current CUDA libraries and tools.
- P40/P100 lack tensor cores; V100 is below current vLLM's compute-capability
  baseline.
- Power connectors and pinouts may not match consumer PCIe cables.
- There may be no display output.

A T4 has modern Turing compatibility and 16 GB VRAM but is relatively slow and
passively cooled. Mixing the RTX 2080 with another GPU does not automatically
pool VRAM; the runtime must explicitly support model parallelism.

## 10. Persistent Services and Backups

Use the repository's Compose stack for MyAI. The API depends on suite
environment values, PostgreSQL, and migrations, so an isolated API Quadlet is
not an equivalent deployment. Convert the complete stack only after its
database, secrets, network, health checks, and storage dependencies are
represented. Fully qualify release images, for example
`docker.io/myaitech/core-api:0.1.0-rc.2`.

Rootless Quadlets live under:

```text
~/.config/containers/systemd/
```

Enable user lingering when services must run without an active login:

```bash
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
```

Back up externally:

- Git repositories and reviewed configuration.
- Database dumps.
- Custom datasets and their metadata.
- LoRA adapters and irreplaceable merged models.
- MLflow metadata and evaluation reports.
- Encrypted secrets.

Do not copy a live MLflow SQLite file as a backup. Stop MLflow first, use
SQLite's backup API, or move the backend store to PostgreSQL for online backup.

Usually do not back up Podman graph storage, scratch data, or publicly
downloadable base models.

## 11. API Keys and Secrets

Do not place provider keys in Git repositories, Compose files, shell history,
or generated bootstrap bundles.

Create a local secret file:

```bash
install -d -m 0700 ~/.config/myai
install -m 0600 /dev/null ~/.config/myai/providers.env
nano ~/.config/myai/providers.env
```

Example names only:

```dotenv
OPENAI_API_KEY=replace-locally
ANTHROPIC_API_KEY=replace-locally
GOOGLE_API_KEY=replace-locally
HF_TOKEN=replace-locally
```

For systemd or Quadlet services, reference an environment file rather than
embedding values in unit definitions. For interactive use, prefer KeePassXC,
1Password CLI, `pass`, or another local secret manager. For encrypted files in
a private infrastructure repository, use SOPS with age and keep the age key
outside the repository.

Rotate the provider keys currently present in ignored development artifacts on
the Windows workstation immediately. Do not wait for the Zorin migration.
Remove secrets from generated artifacts and backups, and verify with repository
history inspection or a secret scanner that they were never committed or
shared.

## 12. OpenCode Sessions Across Devices

There are two supported patterns. Do not synchronize OpenCode's live SQLite
database with OneDrive, Syncthing, Dropbox, NFS, or a shared NVMe mount.

### One-time session transfer

On the source device:

```bash
opencode session list
SESSION_ID=ses_replace_with_the_listed_id
opencode export "$SESSION_ID" > session.json
```

Transfer the JSON securely, clone the same repository on the destination, then
run from that repository:

```bash
opencode import session.json
IMPORTED_SESSION_ID=ses_replace_with_id_printed_by_import
opencode --session "$IMPORTED_SESSION_ID"
```

Use the session ID printed by `opencode import`; imports preserve the exported
ID and may update an existing session with that ID. Export/import transfers
session messages and parts. It does not transfer the
repository checkout, provider credentials, global configuration, plugins, or
snapshot store. Unsanitized exports can contain source, paths, shell output,
patches, and prompts; protect them like development data.

Use `--sanitize` only when disclosure safety is more important than faithful
continuation:

```bash
opencode export "$SESSION_ID" --sanitize > session-redacted.json
```

### Live shared backend

The preferred multi-device workflow is to keep the repository, OpenCode state,
credentials, and tools on the Zorin workstation and attach remotely.

On Zorin:

```bash
export OPENCODE_SERVER_PASSWORD='<strong-secret-from-your-password-manager>'
opencode serve --hostname 127.0.0.1 --port 4096
```

From the other workstation, create an SSH tunnel:

```bash
ssh -N -L 4096:127.0.0.1:4096 user@zorin-host
```

In another terminal on the client:

```bash
export OPENCODE_SERVER_PASSWORD='<same-secret>'
opencode attach http://127.0.0.1:4096 \
  --dir /absolute/path/on-the-zorin-host \
  --continue
```

The server does not need to start in the project directory when the client uses
`--dir`. That absolute path belongs to the server. Attached clients use the
server's working tree, session database, provider credentials, MCP/LSP
processes, and shell tools. This is centralized access, not filesystem
synchronization.

Tailscale or WireGuard can replace the SSH transport, but OpenCode's server is
plain HTTP. Keep password authentication enabled and do not expose port 4096
directly to the internet. A TLS reverse proxy is required if traffic leaves an
encrypted VPN/tunnel.

OpenCode's `/share` feature publishes a conversation for viewing. It is not a
private multi-device backend and should not be used for source-bearing sessions
unless public disclosure is intended. Use global config to keep sharing manual
or disabled:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "share": "disabled"
}
```

After changing OpenCode configuration, quit and restart OpenCode.

## 13. Validation Checklist

### Storage and Podman

```bash
findmnt /srv/ai
df -h /srv/ai
podman info --format '{{.Host.Security.Rootless}}'
podman info --format '{{.Store.GraphDriverName}}'
podman info --format '{{.Store.GraphRoot}}'
podman system df
```

Expected:

```text
true
overlay
/srv/ai/podman/storage
```

### GPU

```bash
nvidia-smi
nvidia-ctk cdi list
podman run --rm \
  --device nvidia.com/gpu=all \
  docker.io/nvidia/cuda:12.8.1-base-ubuntu24.04 \
  nvidia-smi
```

### Local inference

```bash
curl http://127.0.0.1:11434/api/tags | jq
ollama ps
watch -n 2 nvidia-smi
```

### MyAI suite

The full build requires sibling checkouts named `kairos-studio`,
`kairos-council`, `MyAIDE`, and `MyAI-KnowLedger` under the same parent as the
Core checkout. From the Core repository, first inspect the resolved paths:

```bash
bash ./scripts/multi-repo-workflow.sh --action list
```

On a clean workstation, the manifest-driven helper can clone missing sibling
repositories and fast-forward existing clean default-branch checkouts:

```bash
bash ./scripts/multi-repo-workflow.sh --action sync --targets all
```

See `docs/workspace-orchestration-helper.md` for MyAIDE integration, dry-run
events, custom repositories, and reusable pipelines.

For a standalone Core checkout, build only Core:

```bash
bash ./scripts/multi-repo-workflow.sh \
  --action build \
  --targets core-api,core-frontend \
  --engine podman
```

For release-image acceptance, configure `myai-suite/.env` with immutable
`0.1.0-rc.2` image tags, then run from `myai-suite`:

```bash
podman compose --profile all pull
podman compose --profile all up -d postgres
bash ./migrate-db.sh apply
podman compose --profile all up -d --no-build --force-recreate --remove-orphans
```

The current `deploy.sh` helper always passes `--build`; do not use it to prove
that pulled release images work independently of local source.

Use immutable suite tags such as `0.1.0-rc.2` for acceptance testing. Do not
promote `stable` until the full Zorin smoke test and migration checks pass.

## 14. Recommended Setup Order

1. Update UEFI, Intel microcode, Zorin, and the kernel; validate stability.
2. Format and mount the secondary NVMe at `/srv/ai`.
3. Configure the storage layout and free-space monitoring.
4. Install rootless Podman and set `graphroot` before pulling images.
5. Install and validate the NVIDIA desktop driver.
6. Install NVIDIA Container Toolkit and validate CDI with rootless Podman.
7. Install `llama.cpp` and benchmark Qwen3-4B Q5_K_M or Q6_K.
8. Install Ollama and test `qwen3:4b` at 4K context.
9. Add Open WebUI using a pinned container version.
10. Pull and smoke-test MyAI `0.1.0-rc.2` with the no-build Compose commands
    above.
11. Create isolated Hugging Face inference and training environments.
12. Fine-tune a 0.6B/1.7B model before attempting 4B QLoRA.
13. Add MLflow, DVC, and MyAI-specific evaluation datasets.
14. Configure OpenCode export/import or an SSH-tunneled live server.
15. Add external backups and copy only newly rotated provider credentials.

## References

- [NVIDIA driver installation][nvidia-driver]
- [NVIDIA Container Toolkit][nvidia-toolkit]
- [NVIDIA CDI support][nvidia-cdi]
- [Podman storage configuration][podman-storage]
- [Podman Quadlet][podman-quadlet]
- [Ollama GPU support][ollama-gpu]
- [Ollama FAQ and model storage][ollama-faq]
- [llama.cpp CUDA build][llama-cuda]
- [Hugging Face downloads][hf-downloads]
- [Transformers bitsandbytes][transformers-bnb]
- [PEFT][peft]
- [TRL][trl]
- [Accelerate][accelerate]
- [MLflow tracking][mlflow]
- [DVC][dvc]
- [OpenCode CLI][opencode-cli]
- [OpenCode server][opencode-server]
- [OpenCode sharing][opencode-sharing]

[nvidia-driver]: https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/
[nvidia-toolkit]: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
[nvidia-cdi]: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html
[podman-storage]: https://github.com/containers/storage/blob/main/docs/containers-storage.conf.5.md
[podman-quadlet]: https://docs.podman.io/en/latest/markdown/podman-quadlet.1.html
[ollama-gpu]: https://docs.ollama.com/gpu
[ollama-faq]: https://docs.ollama.com/faq
[llama-cuda]: https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
[hf-downloads]: https://huggingface.co/docs/huggingface_hub/en/guides/download
[transformers-bnb]: https://huggingface.co/docs/transformers/en/quantization/bitsandbytes
[peft]: https://huggingface.co/docs/peft/
[trl]: https://huggingface.co/docs/trl/
[accelerate]: https://huggingface.co/docs/accelerate/
[mlflow]: https://mlflow.org/docs/latest/ml/tracking/
[dvc]: https://dvc.org/doc/start
[opencode-cli]: https://opencode.ai/docs/cli/
[opencode-server]: https://opencode.ai/docs/server/
[opencode-sharing]: https://opencode.ai/docs/share/
