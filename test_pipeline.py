from reel_generator import ReelPipeline

# Initialize
pipeline = ReelPipeline()

# Test with the test video
result = pipeline.process_single_video(
    video_path="input_videos/test.mp4",
    scene_description="A colorful abstract pattern representing the chaos and beauty of life",
    mood="inspirational",
    filter_type="cinematic"
)

if result:
    print(f"\n🎉 SUCCESS! Your reel is ready: {result}")
else:
    print("\n❌ Something went wrong. Check the errors above.")