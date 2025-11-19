#!/usr/bin/env python3
"""
Viral Reel Generator - Complete Pipeline
Generates emotional interpretation reels from video clips
"""

import os
import subprocess
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Pipeline configuration"""
    # Directories
    INPUT_DIR = os.getenv("INPUT_DIR", "input_videos")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output_reels")
    AUDIO_DIR = os.getenv("AUDIO_TEMP_DIR", "audio_temp")
    
    # Video settings
    TARGET_DURATION = (60, 120)  # seconds
    
    # TTS settings (using Piper)
    PIPER_MODEL = os.getenv("PIPER_MODEL", "en_US-lessac-medium")
    PIPER_VOICE_SPEED = float(os.getenv("PIPER_VOICE_SPEED", "0.9"))
    
    # FFmpeg settings (support portable paths)
    FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
    FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
    VIDEO_CODEC = os.getenv("VIDEO_CODEC", "libx264")
    AUDIO_CODEC = os.getenv("AUDIO_CODEC", "aac")
    
    # Claude API
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    def __init__(self):
        # Create directories
        for d in [self.INPUT_DIR, self.OUTPUT_DIR, self.AUDIO_DIR]:
            Path(d).mkdir(exist_ok=True)


# ============================================================================
# STEP 1: VIDEO PROCESSING
# ============================================================================

class VideoProcessor:
    """Handles video manipulation with FFmpeg"""
    
    @staticmethod
    def extract_silent_video(input_path: str, output_path: str) -> bool:
        """Remove audio from video"""
        try:
            cmd = [
                Config.FFMPEG_PATH, "-i", input_path,
                "-an",  # Remove audio
                "-c:v", "copy",  # Copy video codec (fast)
                "-y",  # Overwrite
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Extracted silent video: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg error: {e.stderr.decode()}")
            return False
    
    @staticmethod
    def get_video_duration(video_path: str) -> float:
        """Get video duration in seconds"""
        cmd = [
            Config.FFPROBE_PATH, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    
    @staticmethod
    def apply_creative_filter(input_path: str, output_path: str, filter_type: str = "cinematic") -> bool:
        """Apply filters to make content more unique"""
        filters = {
            "cinematic": "eq=contrast=1.2:brightness=0.05:saturation=1.1,unsharp=5:5:1.0",
            "vintage": "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3,vignette",
            "dreamy": "gblur=sigma=2,eq=contrast=0.9:brightness=0.1:saturation=1.3",
            "dramatic": "curves=vintage,unsharp=7:7:1.5"
        }
        
        vf = filters.get(filter_type, filters["cinematic"])
        
        try:
            cmd = [
                Config.FFMPEG_PATH, "-i", input_path,
                "-vf", vf,
                "-c:v", Config.VIDEO_CODEC,
                "-preset", "medium",
                "-y",
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Applied '{filter_type}' filter")
            return True
        except subprocess.CalledProcessError:
            return False
    
    @staticmethod
    def merge_audio_video(video_path: str, audio_path: str, output_path: str) -> bool:
        """Combine video and narration audio"""
        try:
            cmd = [
                Config.FFMPEG_PATH,
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", Config.AUDIO_CODEC,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",  # Match shortest stream
                "-y",
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Merged video + audio: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Merge failed: {e.stderr.decode()}")
            return False


# ============================================================================
# STEP 2: NARRATION GENERATION (CLAUDE)
# ============================================================================

class NarrationGenerator:
    """Generate emotional interpretations using Claude"""
    
    SYSTEM_PROMPT = """You are an expert cinematic narrator who creates emotionally powerful 
interpretations for short clips (60–120 seconds).

YOUR TASK:
1. Create a fully original narration that FEELS like deep interpretation, not a summary.
2. Make it sound like a wise storyteller explaining the hidden meaning.
3. DO NOT describe the actual clip, only interpret the emotion behind it.
4. Use simple but poetic English.
5. Length: 110–140 words for reels.
6. Format the output as:

HOOK: [1 powerful line]

MEANING:
[4–6 emotional lines explaining the deeper truth]

ENDING: [1 strong closing line]

VOICE_NOTES:
- Pace: [slow/medium/fast]
- Tone: [calm/intense/warm]
- Pauses: [where to breathe]

Make it impactful, universal, and relatable."""
    
    def __init__(self, api_key: str = None):
        # Check multiple possible environment variable names
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("claude_api_key") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("API key not found! Set ANTHROPIC_API_KEY in .env file")
        self.client = Anthropic(api_key=api_key)
    
    def generate_narration(self, scene_description: str, mood: str = "inspirational") -> dict:
        """Generate narration from scene description"""
        
        user_prompt = f"""Scene: {scene_description}

Desired mood: {mood}

Create the narration now."""
        
        try:
            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=1000,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            narration_text = response.content[0].text
            print("✅ Generated narration from Claude")
            
            return self._parse_narration(narration_text)
            
        except Exception as e:
            print(f"❌ Claude API error: {e}")
            return None
    
    def _parse_narration(self, text: str) -> dict:
        """Parse Claude's response into structured format"""
        lines = text.strip().split('\n')
        result = {
            "hook": "",
            "meaning": "",
            "ending": "",
            "full_script": text,
            "voice_notes": ""
        }
        
        current_section = None
        for line in lines:
            line = line.strip()
            if line.startswith("HOOK:"):
                current_section = "hook"
                result["hook"] = line.replace("HOOK:", "").strip().strip('"')
            elif line.startswith("MEANING:"):
                current_section = "meaning"
            elif line.startswith("ENDING:"):
                current_section = "ending"
                result["ending"] = line.replace("ENDING:", "").strip().strip('"')
            elif line.startswith("VOICE_NOTES:"):
                current_section = "voice_notes"
            elif current_section == "meaning" and line:
                result["meaning"] += line + "\n"
        
        result["meaning"] = result["meaning"].strip()
        return result


# ============================================================================
# STEP 3: TEXT-TO-SPEECH
# ============================================================================

class TTSEngine:
    """Text-to-speech using multiple engines"""
    
    @staticmethod
    def generate_speech_pyttsx3(text: str, output_path: str) -> bool:
        """Generate speech using pyttsx3 (Windows built-in, works offline)"""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # Configure voice (slower, deeper for emotional impact)
            engine.setProperty('rate', 150)  # Speed (default 200)
            engine.setProperty('volume', 1.0)
            
            # Get available voices and prefer female voice if available
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id)  # Usually female voice
            
            # Save to file
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
            print(f"✅ Generated TTS audio: {output_path}")
            return True
        except Exception as e:
            print(f"❌ pyttsx3 TTS error: {e}")
            return False
    
    @staticmethod
    def generate_speech_piper(text: str, output_path: str, model: str = None) -> bool:
        """Generate speech using Piper TTS"""
        model = model or Config.PIPER_MODEL
        
        try:
            # Piper command: echo "text" | piper --model MODEL --output_file output.wav
            cmd = f'echo "{text}" | piper --model {model} --output_file {output_path}'
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            print(f"✅ Generated TTS audio: {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Piper TTS error: {e}")
            return False
    
    @staticmethod
    def generate_speech(text: str, output_path: str, engine: str = "auto") -> bool:
        """Auto-detect and use best available TTS engine"""
        if engine == "pyttsx3" or engine == "auto":
            # Try pyttsx3 first (most reliable on Windows)
            if TTSEngine.generate_speech_pyttsx3(text, output_path):
                return True
        
        if engine == "piper" or engine == "auto":
            # Fallback to Piper
            if TTSEngine.generate_speech_piper(text, output_path):
                return True
        
        print("❌ No TTS engine available!")
        return False
    
    @staticmethod
    def adjust_audio_speed(input_path: str, output_path: str, speed: float = 0.9):
        """Slow down audio for emotional impact"""
        try:
            cmd = [
                Config.FFMPEG_PATH, "-i", input_path,
                "-filter:a", f"atempo={speed}",
                "-y",
                output_path
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✅ Adjusted audio speed to {speed}x")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Audio speed adjustment failed: {e.stderr}")
            # If speed adjustment fails, just copy the original file
            import shutil
            shutil.copy(input_path, output_path)
            print(f"✅ Using original audio speed instead")
            return True


# ============================================================================
# MAIN PIPELINE
# ============================================================================

class ReelPipeline:
    """Complete automated pipeline"""
    
    def __init__(self):
        self.config = Config()
        self.video = VideoProcessor()
        self.narrator = NarrationGenerator()
        self.tts = TTSEngine()
    
    def process_single_video(self, 
                            video_path: str, 
                            scene_description: str,
                            mood: str = "inspirational",
                            filter_type: str = "cinematic") -> str:
        """Process one video through complete pipeline"""
        
        video_name = Path(video_path).stem
        print(f"\n🎬 Processing: {video_name}")
        
        # Step 1: Extract silent video
        silent_path = f"{self.config.AUDIO_DIR}/{video_name}_silent.mp4"
        if not self.video.extract_silent_video(video_path, silent_path):
            return None
        
        # Step 2: Apply creative filter (optional)
        filtered_path = f"{self.config.AUDIO_DIR}/{video_name}_filtered.mp4"
        self.video.apply_creative_filter(silent_path, filtered_path, filter_type)
        
        # Step 3: Generate narration
        narration = self.narrator.generate_narration(scene_description, mood)
        if not narration:
            return None
        
        # Step 4: Generate TTS
        audio_path = f"{self.config.AUDIO_DIR}/{video_name}_narration.wav"
        script = f"{narration['hook']}\n\n{narration['meaning']}\n\n{narration['ending']}"
        
        if not self.tts.generate_speech_piper(script, audio_path):
            return None
        
        # Step 5: Adjust audio speed
        slow_audio = f"{self.config.AUDIO_DIR}/{video_name}_narration_slow.wav"
        self.tts.adjust_audio_speed(audio_path, slow_audio, Config.PIPER_VOICE_SPEED)
        
        # Step 6: Merge video + audio
        final_path = f"{self.config.OUTPUT_DIR}/{video_name}_final.mp4"
        if self.video.merge_audio_video(filtered_path, slow_audio, final_path):
            print(f"🎉 SUCCESS! Final reel: {final_path}\n")
            return final_path
        
        return None
    
    def batch_process(self, video_descriptions: list):
        """Process multiple videos"""
        results = []
        for item in video_descriptions:
            result = self.process_single_video(
                item["video_path"],
                item["description"],
                item.get("mood", "inspirational"),
                item.get("filter", "cinematic")
            )
            results.append(result)
        
        print(f"\n✅ Completed {len([r for r in results if r])} / {len(results)} videos")
        return results


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize pipeline
    pipeline = ReelPipeline()
    
    # Example: Process a single video
    result = pipeline.process_single_video(
        video_path="input_videos/example_clip.mp4",
        scene_description="A person standing alone on a mountain peak at sunrise, looking at the horizon",
        mood="inspirational",
        filter_type="cinematic"
    )
    
    # Example: Batch processing
    batch_videos = [
        {
            "video_path": "input_videos/clip1.mp4",
            "description": "A lone tree surviving in a desert storm",
            "mood": "resilience",
            "filter": "dramatic"
        },
        {
            "video_path": "input_videos/clip2.mp4",
            "description": "Ocean waves crashing against rocks during sunset",
            "mood": "calm",
            "filter": "cinematic"
        }
    ]
    
    # pipeline.batch_process(batch_videos)
    
    print("\n🚀 Pipeline ready! Edit the examples above and run.")