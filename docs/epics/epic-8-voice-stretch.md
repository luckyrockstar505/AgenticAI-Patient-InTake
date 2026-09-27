# Epic 8: Voice (Stretch)

**Track:** A/B  
**Goal:** Add real-time voice: streaming speech-to-text into the same graph and spoken replies.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [8.1](../stories/8.1.voice-websocket-transcribe-streaming.md) | Voice: WebSocket + Transcribe streaming | B | 5.1 | L |
| [8.2](../stories/8.2.voice-polly-tts-turn-taking.md) | Voice: Polly TTS & turn-taking | A | 8.1 | M |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
