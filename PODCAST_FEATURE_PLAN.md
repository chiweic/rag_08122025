# Podcast Generation Feature - Implementation Plan

**Status:** 📋 Planned for Next Milestone
**Priority:** Medium-High
**Estimated Timeline:** 1-2 weeks
**Target Users:** All users seeking audio-based learning

---

## 🎯 Feature Overview

Generate short, conversational podcasts (2-3 minutes) from user queries and top-ranked source content. Transform Buddhist teachings from text into engaging audio format for:
- Commute listening
- Meditation preparation
- Accessibility (visual impairment, reading difficulty)
- Multi-modal learning reinforcement

---

## 📊 Implementation Phases

### **Phase 1: MVP - Single-Voice TTS Podcast** ⭐ Priority
**Timeline:** 1-2 days
**Goal:** Basic podcast generation with single narrator

#### Features:
- ✅ Generate conversational script from query + top-1 chunk
- ✅ Convert to audio using OpenAI TTS (tts-1-hd, "nova" voice)
- ✅ Download as MP3 file
- ✅ Simple audio player modal in frontend
- ✅ Save podcast history to database

#### Components to Build:
1. **Backend Module:** `podcast_generator.py` (~200 lines)
   - `PodcastGenerator` class
   - `generate_script()` - LLM-based script generation
   - `text_to_speech()` - OpenAI TTS integration
   - `generate_podcast()` - Full pipeline

2. **API Endpoint:** `POST /podcast/generate` (~50 lines in api.py)
   - Validates last query exists
   - Calls PodcastGenerator
   - Returns streaming MP3 response
   - Saves to database

3. **Database Migration:** `003_podcast_episodes.sql` (~50 lines)
   ```sql
   CREATE TABLE podcast_episodes (
       id SERIAL PRIMARY KEY,
       user_id UUID REFERENCES users(id),
       user_email VARCHAR(255),
       episode_id VARCHAR(100) UNIQUE,
       query TEXT NOT NULL,
       source_chunk_id VARCHAR(200),
       script TEXT NOT NULL,
       audio_url TEXT,
       duration_seconds INTEGER,
       format VARCHAR(20) DEFAULT 'single',
       play_count INTEGER DEFAULT 0,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

4. **Frontend UI:** (~150 lines in index.html)
   - "🎙️ 產生播客" button in answer actions
   - Audio player modal with:
     - Waveform/progress bar
     - Play/pause controls
     - Download button
     - Script display (expandable)
     - Add to favorites
   - Loading state during generation

#### Script Generation Prompt Template:
```python
prompt = f"""你是一位佛學導師，要為聽眾錄製一段2-3分鐘的短播客。

問題：{query}
參考資料標題：{source_title}
參考內容：{source_text}

請撰寫一段溫暖、口語化的播客講稿，包含：
1. 開場（問候聽眾，重述問題）
2. 核心解說（用淺顯易懂的方式解釋，引用參考資料）
3. 實用建議（如何應用到日常生活）
4. 結尾（鼓勵與祝福）

語氣：親切、溫暖、專業
長度：約500-700字
風格：像在跟朋友聊天，不要太正式
```

#### Cost Estimate (per podcast):
- GPT-4 script generation: ~$0.03
- OpenAI TTS-1-HD (700 chars): ~$0.02
- **Total: ~$0.05 per episode**
- For 1000 users @ 1 podcast/day: **$50/day** ✅ Affordable

---

### **Phase 2: Enhanced Dialogue Podcast** 🎙️
**Timeline:** 3-5 days
**Goal:** Two-voice conversational format (inspired by NotebookLM)

#### Additional Features:
- ✅ Two-speaker dialogue (host + expert)
- ✅ Background meditation music mixing
- ✅ More engaging conversation flow
- ✅ Natural question-answer format

#### Script Format:
```json
{
  "segments": [
    {"speaker": "host", "text": "歡迎來到佛學智慧分享...", "emotion": "welcoming"},
    {"speaker": "expert", "text": "根據聖嚴法師的開示...", "emotion": "thoughtful"},
    ...
  ]
}
```

#### Tech Stack Additions:
- **Audio Mixing:** pydub, ffmpeg
- **TTS Voices:**
  - Host: "alloy" (curious, friendly)
  - Expert: "nova" (knowledgeable, calm)
- **Background Music:** Royalty-free meditation tracks (Creative Commons)

#### Audio Processing Pipeline:
```python
1. Generate dialogue segments
2. For each segment:
   - Select voice based on speaker
   - Generate TTS audio
   - Add 0.5s pause between exchanges
3. Load background music (reduced volume -25dB)
4. Mix dialogue over background music
5. Normalize final audio
6. Export as MP3
```

---

### **Phase 3: Personalization & Library** 📚
**Timeline:** 1 week
**Goal:** Full podcast management and discovery

#### Features:
- ✅ Podcast library in Learning Journey panel
- ✅ Playback history tracking
- ✅ Favorite/bookmark episodes
- ✅ Listening time statistics
- ✅ Share podcast links
- ✅ Playback speed control (0.75x, 1x, 1.25x, 1.5x)
- ✅ Timestamp bookmarks with notes
- ✅ Recommended podcasts based on user interests

#### Additional Database Tables:
```sql
CREATE TABLE podcast_bookmarks (
    id SERIAL PRIMARY KEY,
    episode_id VARCHAR(100) REFERENCES podcast_episodes(episode_id),
    user_email VARCHAR(255),
    timestamp_seconds INTEGER,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE podcast_listens (
    id SERIAL PRIMARY KEY,
    episode_id VARCHAR(100) REFERENCES podcast_episodes(episode_id),
    user_email VARCHAR(255),
    listen_duration_seconds INTEGER,
    playback_speed DECIMAL(3,2) DEFAULT 1.0,
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Learning Journey Integration:
- New statistics card: "🎧 播客聆聽時數"
- Podcast library section with filters:
  - Recent episodes
  - Favorites
  - By topic
  - By duration
- Achievement: "首次收聽", "累積聆聽10小時", etc.

---

## 🎨 UI/UX Design Specifications

### **1. Podcast Generation Button**
Location: Answer action bar (next to Summary, Quiz buttons)

```html
<button id="podcastBtn" class="action-button">
  <i data-lucide="podcast" class="w-4 h-4"></i>產生播客
</button>
```

States:
- Default: "🎙️ 產生播客"
- Loading: "⏳ 生成中..." (disabled)
- Error: Show error toast

### **2. Audio Player Modal**

```
┌─────────────────────────────────────────────────┐
│  🎙️ 佛學智慧播客                    [X]         │
├─────────────────────────────────────────────────┤
│  📖 什麼是禪修？                                 │
│  來源：《禪修入門》聖嚴法師                      │
│  ───────────────────────────────────────────    │
│                                                  │
│  ▶️ 🔊 ━━━━━━●━━━━━━━━ 2:34 / 5:12           │
│                                                  │
│  [⏮️ 後退10s] [⏯️ 播放/暫停] [⏭️ 前進10s]        │
│  [🔁 重播] [⚡ 1.0x] [⬇️ 下載MP3]              │
│                                                  │
│  ───────────────────────────────────────────    │
│  📝 講稿 [展開 ▼]                               │
│  ───────────────────────────────────────────    │
│                                                  │
│  ⭐ 加入最愛  📤 分享  🔖 新增書籤              │
└─────────────────────────────────────────────────┘
```

Features:
- Waveform visualization (optional, using wavesurfer.js)
- Seek bar with time labels
- Volume control
- Playback speed selector (0.75x, 1.0x, 1.25x, 1.5x, 2.0x)
- Script expandable section
- Download button (saves as `podcast_YYYY-MM-DD_QUERY.mp3`)

### **3. Podcast Library (in Learning Journey Panel)**

```
個人學習歷程
├─ 📊 統計資料
├─ 📝 測驗歷史
├─ 🎧 播客收聽記錄  ← NEW
│   ├─ 總收聽時數: 5.2 小時
│   ├─ 已收聽: 12 集
│   ├─ 我的最愛: 3 集
│   │
│   └─ 播客列表
│       ├─ [⭐] 什麼是禪修？ (5:12) - 2天前
│       ├─ [ ] 四聖諦的意義 (4:38) - 1週前
│       └─ [⭐] 如何開始打坐？ (3:45) - 2週前
│
└─ 🏆 成就徽章
```

---

## 🔧 Technical Architecture

### **Backend Stack:**
```
podcast_generator.py (new)
  ├─ PodcastGenerator class
  │   ├─ generate_script() → LLM
  │   ├─ text_to_speech() → OpenAI TTS API
  │   ├─ mix_audio() → pydub (Phase 2)
  │   └─ generate_podcast() → orchestration
  │
api.py (updated)
  ├─ POST /podcast/generate
  ├─ GET /podcast/history
  ├─ GET /podcast/{episode_id}
  ├─ POST /podcast/{episode_id}/favorite
  └─ POST /podcast/{episode_id}/bookmark

db_helpers.py (updated)
  ├─ save_podcast_episode()
  ├─ get_podcast_history()
  ├─ track_podcast_listen()
  └─ get_podcast_statistics()
```

### **Frontend Stack:**
```javascript
// New functions in index.html

async function generatePodcast()
async function showPodcastPlayer(audioUrl, script, metadata)
async function loadPodcastLibrary()
function updatePodcastProgress(episodeId, currentTime)
function addPodcastBookmark(episodeId, timestamp, note)
```

### **Dependencies to Add:**
```txt
# requirements.txt additions
pydub==0.25.1              # Audio manipulation
ffmpeg-python==0.2.0       # Audio encoding
```

### **System Requirements:**
- FFmpeg installed on server (for audio processing)
- Storage for audio files (local or S3)
- OpenAI API key with TTS access

---

## 🚀 Alternative TTS Providers (for comparison)

### **Option 1: OpenAI TTS** ⭐ Recommended
- **Pros:** Excellent Chinese support, easy integration, good quality
- **Cons:** Moderate cost
- **Cost:** $0.030/1K chars (tts-1-hd)
- **Voices:** alloy, echo, fable, onyx, nova, shimmer

### **Option 2: Google Cloud TTS**
- **Pros:** Very natural WaveNet voices, zh-TW support, cheaper
- **Cons:** Requires GCP setup
- **Cost:** $16/1M chars (WaveNet) = $0.016/1K chars
- **Voices:** Multiple zh-TW options (male/female)

### **Option 3: Azure TTS**
- **Pros:** Neural voices excellent quality, good Chinese
- **Cons:** Complex pricing, requires Azure account
- **Cost:** ~$0.016/1K chars (Neural)
- **Voices:** zh-TW-HsiaoChenNeural, zh-TW-YunJheNeural

### **Option 4: Edge TTS (Free!)** 💰
- **Pros:** Free, decent quality, zh-TW support
- **Cons:** Unofficial API, may be rate-limited
- **Cost:** $0 (free)
- **Library:** edge-tts (Python)

**Recommendation:** Start with **OpenAI TTS** for MVP, evaluate **Google Cloud TTS** for Phase 2 cost optimization.

---

## 📈 Success Metrics

### **KPIs to Track:**
1. **Engagement:**
   - Podcast generation rate (% of queries → podcast)
   - Average listen completion rate
   - Favorites/bookmark rate

2. **Quality:**
   - User feedback/ratings
   - Average playback speed (indicates content pace)
   - Replay rate

3. **Learning Impact:**
   - Correlation: podcast listening → quiz scores
   - Podcast library growth per user
   - Total listening hours

4. **Technical:**
   - Average generation time
   - TTS API cost per user
   - Audio file storage usage

### **Target Metrics (Phase 1):**
- Generation time: < 45 seconds
- Cost per podcast: < $0.05
- User adoption: 30% of active users try feature in first month
- Listen completion: > 60% finish entire episode

---

## 🎯 Competitive Differentiation

### **vs. NotebookLM Audio Overview:**
| Feature | NotebookLM | Our Podcast |
|---------|-----------|-------------|
| Length | 10-20 minutes | 2-3 minutes ⚡ |
| Focus | Document summary | Query-specific answer |
| Language | English primary | Mandarin-optimized 🇹🇼 |
| Tone | General education | Buddhist reverence 🙏 |
| Integration | Standalone | Learning Journey |
| Cost | Free (Google) | Low-cost ($0.05) |
| Customization | Fixed format | Flexible (single/dialogue) |

### **Our Unique Value:**
- ✅ **Bite-sized:** Perfect for daily practice (2-3 min)
- ✅ **Context-aware:** Understands Buddhist terminology
- ✅ **Personalized:** Based on user's actual question
- ✅ **Integrated:** Part of holistic learning journey
- ✅ **Cultural:** Respectful, appropriate tone for teachings
- ✅ **Accessible:** Makes ancient wisdom audio-friendly

---

## 🛠️ Implementation Checklist

### **Phase 1 MVP (1-2 days):**
- [ ] Create `podcast_generator.py`
  - [ ] `PodcastGenerator` class
  - [ ] Script generation with GPT-4
  - [ ] OpenAI TTS integration
  - [ ] Error handling
- [ ] Create database migration `003_podcast_episodes.sql`
  - [ ] `podcast_episodes` table
  - [ ] Indexes on user_email, created_at
- [ ] Add `db_helpers.py` functions
  - [ ] `save_podcast_episode()`
  - [ ] `get_podcast_history()`
- [ ] Add API endpoint `POST /podcast/generate`
  - [ ] Validate last query
  - [ ] Generate podcast
  - [ ] Stream MP3 response
  - [ ] Save to database
- [ ] Frontend implementation
  - [ ] Add "產生播客" button to answer actions
  - [ ] Create audio player modal
  - [ ] Implement play/pause/seek controls
  - [ ] Add download functionality
  - [ ] Loading states
- [ ] Testing
  - [ ] Test script generation quality
  - [ ] Test audio generation
  - [ ] Test frontend player
  - [ ] Test download
  - [ ] Cost validation

### **Phase 2 Dialogue (3-5 days):**
- [ ] Update script generation for dialogue format
- [ ] Implement dual-voice TTS
- [ ] Add background music mixing
- [ ] Update frontend for dialogue metadata
- [ ] A/B test: single vs dialogue preference

### **Phase 3 Library (1 week):**
- [ ] Create podcast library UI component
- [ ] Add playback tracking
- [ ] Implement favorites/bookmarks
- [ ] Add statistics to Learning Journey
- [ ] Create recommendation algorithm
- [ ] Implement sharing functionality

---

## 🔮 Future Enhancements (Phase 4+)

1. **Voice Cloning (Advanced):**
   - Train on 聖嚴法師's audio teachings
   - Ethical considerations & permissions
   - Ultra-authentic experience

2. **Multi-language Support:**
   - English podcast generation
   - Auto-translation of scripts

3. **Interactive Podcasts:**
   - Embedded quiz questions
   - Pause for reflection prompts
   - Guided meditation segments

4. **Podcast Playlists:**
   - Thematic collections
   - Learning path podcasts
   - Sequential topic series

5. **Community Features:**
   - Share podcasts with other users
   - Podcast discussion comments
   - Collaborative playlists

6. **Offline Mode:**
   - Download for offline listening
   - Sync progress across devices
   - Mobile app integration

7. **Advanced Analytics:**
   - Listening heatmaps
   - Drop-off points analysis
   - Optimize script pacing based on data

---

## 💡 Key Design Principles

1. **Simplicity First:** Start with single-voice, add complexity later
2. **Quality over Quantity:** 3-minute excellent > 10-minute mediocre
3. **Buddhist Appropriateness:** Tone must be respectful, reverent
4. **Integration:** Seamless part of existing learning journey
5. **Accessibility:** Audio makes teachings available to all
6. **Cost-Conscious:** Keep per-episode cost under $0.10

---

## 📝 Notes & Considerations

### **Legal/Ethical:**
- Attribution of source texts in podcast intro
- Copyright for background music (use CC0/royalty-free)
- Voice cloning requires explicit permission
- User data privacy for listening habits

### **Technical Risks:**
- TTS API rate limits (implement queuing)
- Audio file storage costs (compress, use CDN)
- Generation time during peak hours (async processing)
- Script quality variation (A/B test prompts)

### **User Experience:**
- Auto-play consideration (default: no)
- Mobile-friendly player controls
- Accessibility: keyboard controls, screen reader support
- Clear loading states (generation takes 30-60s)

---

## 🎓 Learning Resources

- **NotebookLM Audio Overview:** [Google Blog](https://blog.google/technology/ai/notebooklm-audio-overviews/)
- **OpenAI TTS Docs:** [Platform Docs](https://platform.openai.com/docs/guides/text-to-speech)
- **Google Cloud TTS:** [WaveNet Voices](https://cloud.google.com/text-to-speech/docs/voices)
- **pydub Tutorial:** [Audio Processing](https://github.com/jiaaro/pydub)
- **Audio UX Best Practices:** [Web Audio](https://web.dev/audio-and-video/)

---

## 📞 Contact & Questions

For implementation questions or clarifications, refer to:
- Main project docs: `README.md`, `CLAUDE.md`
- Database schema: `migrations/002_learning_journey.sql`
- API documentation: `http://localhost:8000/docs`

---

**Last Updated:** 2025-11-04
**Document Version:** 1.0
**Status:** 📋 Ready for Implementation - Next Milestone
