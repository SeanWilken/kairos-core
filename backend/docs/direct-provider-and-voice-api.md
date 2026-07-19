# Direct Provider And Voice API

Core now exposes a small backend-facing surface for:

- direct provider chat without a persona wrapper
- STT provider status and transcription
- TTS provider status and synthesis

These endpoints are intended as a first integration layer for daemon/companion use and future playground/tuning UIs.

## Endpoints

- `POST /v1/system/ai/direct-chat`
- `GET /v1/system/voice/status`
- `POST /v1/system/voice/stt`
- `POST /v1/system/voice/tts`

## 1) Direct provider chat

### Request

```json
{
  "provider_id": "openai",
  "model_id": "gpt-4o-mini",
  "system_prompt": "You are a concise assistant.",
  "messages": [
    { "role": "user", "content": "Summarize today's priorities." }
  ],
  "model_profile": "balanced"
}
```

### Response

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T16:00:00+00:00",
    "correlation_id": "req-direct-chat-001"
  },
  "data": {
    "provider_id": "openai",
    "model_id": "gpt-4o-mini",
    "content": "## Priorities\n- finish deploy verification\n- review studio refresh path\n- publish images tonight",
    "usage": {
      "prompt_tokens": 42,
      "completion_tokens": 18,
      "total_tokens": 60
    }
  },
  "error": null
}
```

## 2) Voice status

### Response

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T16:01:00+00:00",
    "correlation_id": "req-voice-status-001"
  },
  "data": {
    "stt": {
      "provider": "whisper_cpp",
      "configured": true,
      "language_default": "en",
      "model": "base"
    },
    "tts": {
      "provider": "piper",
      "configured": true,
      "voice_default": "amy",
      "model": "amy.onnx",
      "format_default": "wav"
    }
  },
  "error": null
}
```

## 3) STT transcription

### Request

- `POST /v1/system/voice/stt`
- Content type: `multipart/form-data`

Fields:

- `file` (required)
- `language` (optional)
- `persist_to_knowledge` (optional, boolean)
- `org_id` (required when persisting)
- `title` (optional)
- `summary` (optional)
- `tags_json` (optional JSON array string)
- `visibility_json` (optional JSON object string)
- `metadata_json` (optional JSON object string)

### Response

```json
{
  "meta": {
    "service": "myai-core-backend",
    "version": "0.1.0",
    "spec_version": "v1",
    "environment": "local",
    "timestamp": "2026-06-04T16:02:00+00:00",
    "correlation_id": "req-stt-001"
  },
  "data": {
    "text": "What tasks do I have today?",
    "provider": "whisper_cpp",
    "language": "en",
    "segments": [],
    "raw": {}
  },
  "error": null
}
```

When `persist_to_knowledge=true`, the response also includes:

```json
{
  "knowledge_entity": {
    "entity_id": "...",
    "kind": "knowledge_node",
    "kind_payload": {
      "subtype": "voice_transcript",
      "transcript": "What tasks do I have today?"
    }
  },
  "audio_storage": {
    "backend": "local",
    "uri": "local://tenant-local/org0/.../meeting.wav",
    "object_key": "tenant-local/org0/.../meeting.wav",
    "size_bytes": 12345
  }
}
```

Persisted transcript fragments can later be discovered through the generic knowledge node surface:

- `GET /v1/knowledge/nodes?org_id=<org_id>&kind=knowledge_node&subtype=voice_transcript`
- `GET /v1/knowledge/nodes/{entity_id}`

## 4) TTS synthesis

### Request

```json
{
  "text": "You have three tasks due today.",
  "voice": "amy",
  "format": "wav",
  "speed": 1.0,
  "pitch": 1.0,
  "gain_db": 0.0
}
```

### Response

Returns raw audio bytes with headers like:

```http
HTTP/1.1 200 OK
Content-Type: audio/wav
Content-Disposition: inline; filename="speech.wav"
```

### TTS persistence guidance

TTS output does not need to be stored by Core.

Recommended model:

- store the text, transcript, chat block, or knowledge fragment
- regenerate audio on demand by re-submitting arbitrary text to `POST /v1/system/voice/tts`

This keeps audio generation stateless and makes it easy for a companion daemon or device client to:

- restart playback
- regenerate with a different voice
- resume a conversation from stored text context
- avoid accumulating large stored audio artifacts unnecessarily

### Companion usage note

The companion can safely treat the voice endpoints as backend-facing integration points:

- `GET /v1/system/voice/status`
- `POST /v1/system/voice/stt`
- `POST /v1/system/voice/tts`

The expected flow is:

1. use STT to capture transcript text when needed
2. store transcript/related knowledge if desired
3. use TTS as a stateless render pass over any arbitrary text at playback time

## Configuration

### STT

```env
MYAI_STT_PROVIDER=whisper_cpp
MYAI_STT_WHISPER_CPP_BIN=/path/to/whisper-cli
MYAI_STT_WHISPER_CPP_MODEL=/path/to/model.bin
MYAI_STT_LANGUAGE=en
```

or:

```env
MYAI_STT_PROVIDER=command
MYAI_STT_COMMAND_TEMPLATE=/path/to/script --input {input} --output {output} --language {language}
```

### TTS

```env
MYAI_TTS_PROVIDER=piper
MYAI_TTS_PIPER_BIN=/path/to/piper
MYAI_TTS_PIPER_MODEL=/path/to/voice.onnx
MYAI_TTS_VOICE=default
MYAI_TTS_FORMAT=wav
```

ElevenLabs option:

```env
MYAI_TTS_PROVIDER=elevenlabs
MYAI_TTS_ELEVENLABS_API_KEY=
MYAI_TTS_ELEVENLABS_VOICE_ID=
MYAI_TTS_ELEVENLABS_MODEL=eleven_turbo_v2_5
MYAI_TTS_ELEVENLABS_BASE_URL=https://api.elevenlabs.io
MYAI_TTS_ELEVENLABS_STABILITY=0.5
MYAI_TTS_ELEVENLABS_SIMILARITY_BOOST=0.75
MYAI_TTS_ELEVENLABS_STYLE=0.0
MYAI_TTS_FORMAT=mp3
```

or:

```env
MYAI_TTS_PROVIDER=command
MYAI_TTS_COMMAND_TEMPLATE=/path/to/script --output {output} --voice {voice} --format {format} --speed {speed} --pitch {pitch} --gain {gain_db}
```

## Notes

- These routes are intended for daemon/backend-facing use.
- They do not yet imply persona-level voice features.
- They are a foundation for later companion UI tuning and MyAI suite integration.

TTS request tuning fields currently accepted include:

- `voice`
- `format`
- `speed`
- `pitch`
- `gain_db`
- `tone`
- `cadence`
- `stability`
- `similarity_boost`
- `style`

Not every provider uses every field. Piper uses a smaller subset today; ElevenLabs can make use of the more expressive voice-style settings.
