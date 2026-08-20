# from typing import Optional

# from faster_whisper import WhisperModel


# class Transcriber:
#     """
#     Marathi / Hindi / English speech-to-text using Faster-Whisper.

#     The important design decisions here are:
#     - small model instead of base for better Indic recognition
#     - CPU INT8 for practical Windows CPU inference
#     - VAD to remove silent/non-speech sections
#     - condition_on_previous_text=False to reduce hallucination propagation
#     - confidence / repetition filtering
#     """

#     def __init__(self):
#         print("Loading Faster-Whisper model: small")

#         self.model = WhisperModel(
#             "small",
#             device="cpu",
#             compute_type="int8",
#             cpu_threads=11,
#             num_workers=1,
#         )

#         print("Faster-Whisper ready.")

#     def transcribe(
#         self,
#         audio_path: str,
#         language: str = "mr",
#     ):

#         print(f"Transcribing: {audio_path}")
#         print(f"Whisper language: {language}")

#         segments, info = self.model.transcribe(
#             audio_path,

#             # Explicit language prevents Whisper from trying
#             # to identify garbage as another language.
#             language=language,

#             # Better decoding quality.
#             beam_size=5,
#             best_of=5,

#             # Very important for this video.
#             # Prevents previous hallucinations from contaminating
#             # later segments.
#             condition_on_previous_text=False,

#             # Voice Activity Detection.
#             # This is the major fix for the huge fake subtitles.
#             vad_filter=True,
#             vad_parameters={
#                 "threshold": 0.45,
#                 "min_silence_duration_ms": 500,
#                 "speech_pad_ms": 250,
#             },

#             # Better timestamp information.
#             word_timestamps=True,

#             # Hallucination / low-confidence protection.
#             no_speech_threshold=0.60,
#             log_prob_threshold=-1.0,
#             compression_ratio_threshold=2.4,

#             # Deterministic decoding.
#             temperature=0.0,
#         )

#         result = []

#         for segment in segments:

#             text = segment.text.strip()

#             # Reject obvious character-level repetition
#             if len(text) >= 20:

#                 compact = (
#                     text
#                     .replace(" ", "")
#                     .replace("।", "")
#                     .replace(".", "")
#                     .replace(",", "")
#                 )

#                 if compact:
#                     unique_chars = len(set(compact))
#                     repetition_ratio = (
#                         unique_chars / len(compact)
#                     )

#                     if repetition_ratio < 0.08:
#                         print(
#                             "Skipping character-level "
#                             "hallucination:",
#                             text,
#                         )
#                         continue

#             if not text:
#                 continue

#             start = float(segment.start)
#             end = float(segment.end)

#             # Ignore punctuation-only hallucinations.
#             cleaned = text.replace(
#                 " ",
#                 "",
#             )

#             punctuation_only = all(
#                 char in "।॥.,!?;:!?-—…|"
#                 for char in cleaned
#             )

#             if punctuation_only:
#                 print(
#                     f"Skipping punctuation hallucination: "
#                     f"[{start:.2f} -> {end:.2f}] {text}"
#                 )
#                 continue

#             # Reject obvious repeated-character hallucinations.
#             words = text.split()

#             if len(words) >= 8:
#                 unique_words = len(
#                     set(words)
#                 )

#                 repetition_ratio = (
#                     unique_words / len(words)
#                 )

#                 if repetition_ratio < 0.20:
#                     print(
#                         f"Skipping repetitive hallucination: "
#                         f"[{start:.2f} -> {end:.2f}] {text}"
#                     )
#                     continue

#             # Ignore extremely short fragments.
#             if end - start < 0.25:
#                 continue

#             result.append(
#                 {
#                     "start": start,
#                     "end": end,
#                     "text": text,
#                 }
#             )

#             print(
#                 f"[{start:.2f} -> {end:.2f}] {text}"
#             )

#         print(
#             f"Transcription complete: "
#             f"{len(result)} segments"
#         )

#         print(
#             f"Detected language: "
#             f"{info.language} "
#             f"({info.language_probability:.2f})"
#         )

#         return {
#             "segments": result,
#             "language": info.language,
#             "language_probability": float(
#                 info.language_probability
#             ),
#         }


# # ---------------------------------------------------------
# # Singleton
# # ---------------------------------------------------------

# _transcriber: Optional[Transcriber] = None


# def get_transcriber() -> Transcriber:

#     global _transcriber

#     if _transcriber is None:
#         _transcriber = Transcriber()

#     return _transcriber


# def transcribe_audio(
#     audio_path: str,
#     language: str = "mr",
# ):
#     """
#     Backward-compatible helper.
#     """

#     return get_transcriber().transcribe(
#         audio_path,
#         language,
#     )




























from typing import Optional

from faster_whisper import (
    WhisperModel,
    BatchedInferencePipeline,
)


class Transcriber:

    def __init__(self):
        print("Loading Faster-Whisper model: small")

        self.model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
            cpu_threads=11,
            num_workers=1,
        )

        # Batched inference improves throughput on supported
        # Faster-Whisper versions.
        self.batched_model = BatchedInferencePipeline(
            model=self.model
        )

        print("Faster-Whisper ready.")

    @staticmethod
    def _is_bad_segment(text: str) -> bool:
        text = text.strip()

        if not text:
            return True

        cleaned = (
            text.replace(" ", "")
            .replace("।", "")
            .replace(".", "")
            .replace(",", "")
        )

        if not cleaned:
            return True

        # punctuation-only / symbol-only output
        if all(
            c in "।॥.,!?;:-—…|"
            for c in cleaned
        ):
            return True

        words = text.split()

        # Repeated-word hallucinations
        if len(words) >= 8:
            counts = {}

            for word in words:
                counts[word] = counts.get(word, 0) + 1

            if max(counts.values()) / len(words) > 0.70:
                return True

        # Repeated-character hallucinations
        if len(cleaned) >= 20:
            if len(set(cleaned)) / len(cleaned) < 0.08:
                return True

        return False

    def transcribe(
        self,
        audio_path: str,
        language: str = "mr",
    ):
        print(f"Transcribing: {audio_path}")
        print(f"Whisper language: {language}")

        segments, info = self.batched_model.transcribe(
            audio_path,
            language=language,

            # Keep accuracy high.
            beam_size=5,

            # Prevent hallucination propagation.
            condition_on_previous_text=False,

            # Softer VAD than before to avoid missing speech.
            vad_filter=True,
            vad_parameters={
                "threshold": 0.35,
                "neg_threshold": 0.20,
                "min_speech_duration_ms": 200,
                "min_silence_duration_ms": 1000,
                "speech_pad_ms": 400,
            },

            # Segment timestamps are enough for SRT.
            word_timestamps=False,

            temperature=0.0,
            no_speech_threshold=0.60,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,

            # Batch size: start conservative on CPU.
            batch_size=8,
        )

        result = []

        for segment in segments:
            text = segment.text.strip()

            start = float(segment.start)
            end = float(segment.end)

            if self._is_bad_segment(text):
                print(
                    f"Skipping hallucination: "
                    f"[{start:.2f} -> {end:.2f}] {text}"
                )
                continue

            if end - start < 0.25:
                continue

            result.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

            print(
                f"[{start:.2f} -> {end:.2f}] {text}"
            )

        print(
            f"Transcription complete: "
            f"{len(result)} segments"
        )

        print(
            f"Detected language: "
            f"{info.language} "
            f"({info.language_probability:.2f})"
        )

        return {
            "segments": result,
            "language": info.language,
            "language_probability": float(
                info.language_probability
            ),
        }


_transcriber: Optional[Transcriber] = None


def get_transcriber() -> Transcriber:
    global _transcriber

    if _transcriber is None:
        _transcriber = Transcriber()

    return _transcriber


def transcribe_audio(
    audio_path: str,
    language: str = "mr",
):
    return get_transcriber().transcribe(
        audio_path,
        language,
    )