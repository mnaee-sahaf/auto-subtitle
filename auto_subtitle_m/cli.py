import os
import ffmpeg
import whisper
import argparse
import warnings
import tempfile
from .utils import filename, str2bool, write_srt

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("video", nargs="+", type=str, help="paths to video files to transcribe")
    parser.add_argument("--model", default="small", choices=whisper.available_models(), help="name of the Whisper model to use")
    parser.add_argument("--output_dir", "-o", type=str, default=".", help="directory to save the outputs")
    parser.add_argument("--output_srt", type=str2bool, default=True, help="whether to output the .srt file along with the video files")
    parser.add_argument("--srt_only", type=str2bool, default=False, help="only generate the .srt file and not create overlayed video")
    parser.add_argument("--verbose", type=str2bool, default=False, help="whether to print out progress and debug messages")
    parser.add_argument("--task", type=str, default="transcribe", choices=["transcribe", "translate"], help="whether to transcribe or translate")
    parser.add_argument("--language", type=str, default="auto", help="Language of the video. Defaults to auto-detection.")

    args = parser.parse_args().__dict__
    model_name: str = args.pop("model")
    output_dir: str = args.pop("output_dir")
    output_srt: bool = args.pop("output_srt")
    srt_only: bool = args.pop("srt_only")
    language: str = args.pop("language")
    
    os.makedirs(output_dir, exist_ok=True)
    
    if model_name.endswith(".en"):
        warnings.warn(f"{model_name} is an English-only model, forcing English detection.")
        args["language"] = "en"
    elif language != "auto":
        args["language"] = language

    model = whisper.load_model(model_name)
    audios = get_audio(args.pop("video"))
    subtitles = get_subtitles(audios, output_srt, output_dir, lambda audio_path: model.transcribe(audio_path, **args))

    if srt_only:
        return

    for path, srt_path in subtitles.items():
        out_path = os.path.join(output_dir, f"{filename(path)}.mp4")
        print(f"Adding subtitles to {filename(path)}...")
        
        video = ffmpeg.input(path)
        audio = video.audio
        ffmpeg.concat(
            video.filter('subtitles', srt_path, force_style="OutlineColour=&H40000000,BorderStyle=3"),
            audio, v=1, a=1
        ).output(out_path).run(quiet=True, overwrite_output=True)
        
        print(f"Saved subtitled video to {os.path.abspath(out_path)}.")


def get_audio(paths):
    temp_dir = tempfile.gettempdir()
    audio_paths = {}
    
    for path in paths:
        print(f"Extracting audio from {filename(path)}...")
        output_path = os.path.join(temp_dir, f"{filename(path)}.wav")
        ffmpeg.input(path).output(output_path, acodec="pcm_s16le", ac=1, ar="16k").run(quiet=True, overwrite_output=True)
        audio_paths[path] = output_path
    
    return audio_paths


def get_subtitles(audio_paths, output_srt, output_dir, transcribe):
    subtitles_path = {}
    
    for path, audio_path in audio_paths.items():
        srt_path = os.path.join(output_dir, f"{filename(path)}.srt")
        print(f"Generating subtitles for {filename(path)}... This might take a while.")
        
        warnings.filterwarnings("ignore")
        result = transcribe(audio_path)
        warnings.filterwarnings("default")
        
        with open(srt_path, "w", encoding="utf-8") as srt:
            write_srt(result["segments"], file=srt)
        
        subtitles_path[path] = srt_path
        print(f"Saved subtitles to {srt_path}")
    
    return subtitles_path


if __name__ == '__main__':
    main()
