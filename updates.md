## processing data notes:

1. **event** and **faq** can use the event from raw_data directly
2. **pdf** divides into:
   - faguquanji: topics generated using deepseek pdf_outlines/deepseek-chat and also at qwen3-next-80b, while deepseek gives more details and qwen3 provide a broader topic detection (use deepseek by default)
   - portable book: topic generated using deepseek at outlines/deepseek-chat
   **notes**
   we have noticed the portable books have both traditional and simplified chinese version, but for some reason, LLM gives different topic suggestions. also when we generated topic, we normalized all to traditional 
3. **audio**, the topics are generated with ~/repository/ddm_audio_srt/funasr as transcriptions, plus deepseek as correction, and topics are located under ddm_audio_outlines/qwen3-next-80b-a3b-instruct
4. **video**, the topics are generated with ~/repository/ddm_tv_audio_srt and topics are located at video_outlines/deepseek-chat. previosu run with none-corrected text are at audio_outlines/qwen3-next-80b-a3b-instruct/
