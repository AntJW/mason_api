import numpy as np
import soundfile as sf
import io
import bisect


def convert_wav_bytes_to_samples(wav_bytes):
    """
    Convert WAV bytes to samples.

    Args:
        wav_bytes (bytes): The WAV bytes.

    Returns:
        tuple: A tuple containing the audio samples and the sample rate.
    """

    with io.BytesIO(wav_bytes) as bio:
        audio, sr = sf.read(bio, dtype="float32")

    # ensure mono
    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    return audio, sr


def calculate_rms_db(audio):
    """
    Calculate (RMS) root mean square in decibels (dB) for audio.

    Args:
        audio (numpy.ndarray): The audio samples.

    Returns:
        float: The RMS in decibels (dB) for the audio.
    """

    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    audio = audio.astype(np.float32)

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio /= peak

    rms = np.sqrt(np.mean(audio**2))
    return 20 * np.log10(rms + 1e-10)


def calculate_rms_db_for_segment(audio, sr, start, end):
    """
    Calculate (RMS) root mean square in decibels (dB) for a segment of audio.

    Args:
        audio (numpy.ndarray): The audio samples.
        sr (int): The sample rate of the audio.
        start (float): The start time of the segment.
        end (float): The end time of the segment.

    Returns:
        float: The RMS in decibels (dB) for the segment.
    """

    start_sample = int(start * sr)
    end_sample = int(end * sr)

    segment = audio[start_sample:end_sample]

    if len(segment) == 0:
        return None

    return calculate_rms_db(segment)


def find_speaker_optimized(word_start, word_end, segments, start_times):
    """
    Find speaker using binary search - O(log n) instead of O(n).

    Args:
        word_start (float): The start time of the word.
        word_end (float): The end time of the word.
        segments (list): The list of segments.
        start_times (list): The list of start times.

    Returns:
        str: The speaker for the word.
    """

    # Find the rightmost segment that starts before or at word_start
    idx = max(0, bisect.bisect_right(start_times, word_start) - 1)

    max_overlap = 0
    assigned_speaker = "UNKNOWN"

    # Only check segments that could possibly overlap
    # Start from idx and look forward until segments start after word_end
    while idx < len(segments) and segments[idx]['start'] < word_end:
        segment = segments[idx]

        # Calculate overlap
        overlap_start = max(word_start, segment['start'])
        overlap_end = min(word_end, segment['end'])
        overlap = max(0, overlap_end - overlap_start)

        # Convert "SPEAKER_00" to "SPEAKER 0", etc.
        speaker_num = segment['speaker'].split("_")[-1]
        speaker = f"SPEAKER {int(speaker_num)}"

        if overlap > max_overlap:
            max_overlap = overlap
            assigned_speaker = speaker

        idx += 1

        # Early exit if segment starts after word ends
        if idx < len(segments) and segments[idx]['start'] >= word_end:
            break

    return assigned_speaker
