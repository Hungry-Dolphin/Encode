import os 
import logging as log 
from mimetypes import guess_type
from subprocess import run, CalledProcessError
import json
from datetime import datetime
from tracemalloc import start
from loading import sprites
from asyncio import subprocess as asy_sub
import itertools
import threading
import time
import sys

class Encode:
    list_of_files = list()
    all_video = dict()
    done_encoding = False

    def __init__(self, location, debug_enable, *kwargs, **args) -> None:       
        # Enable logging
        logger = log.getLogger('Encode logger')
        ch = log.StreamHandler()
        formatter = log.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)

        # Option to make the logger display less junk
        if debug_enable:
            logger.setLevel(log.DEBUG)
            ch.setLevel(log.DEBUG)
        else:
            logger.setLevel(log.WARNING)
            ch.setLevel(log.INFO)

        # Set base values 
        self.logger = logger
        self.path = location

        # Start logging
        logger.addHandler(ch)
        logger.debug("Logging started")

        # Fill up the file dir 
        self.discover_files(self.path)
        
        # Filter out the video files
        self.get_video_files()

    def discover_files(self, path):
        # Get all base folder files
        base_files = os.listdir(path)

        for file in base_files:
            self.logger.debug(f"{file}")
            # If the file is actually a dir look for all files inside of it
            if os.path.isdir(os.path.join(path, file)):
                self.logger.info(f"{file} is a directory")
                # Get the path to this dir
                folder_path = os.path.join(path, file)
                self.discover_files(folder_path)
                continue

            self.list_of_files.append(os.path.join(path, file))

    def get_video_files(self):
        # Iterate though all files
        for file in self.list_of_files:
            # Guess the type of file it is
            file_type = guess_type(file, strict=True)[0]
            
            if 'video' in file_type:
                # I could have just saved it as a list and checked what kind of encoding was used later
                # However I am not a fan of lists 
                encoding = file_type.split("/")[1]
                self.logger.debug(f"{file} is a video with {encoding} encoding")
                self.all_video[f'{file}'] = encoding


    def encode_videos(self):
        for video, encoding in self.all_video.items():
            self.logger.debug(f"Now working on {video}")

            # Call ffprobe for the video     
            ffprobe = self.ffprobe_video(video)
            
            # Check if the ffprobe function was succesful otherwise skip it
            if not ffprobe: continue

            # In our case we only want a video and audio stream, any other streams are out of scope for now
            try:
                video_type = ffprobe[0]
                audio_type = ffprobe[1]
            except Exception as e:
                self.logger.error(f"Video {video} does not have 2 streams \b Did you download hardsubbed content?, skipping")
                continue

            if video_type["codec_name"] != "h265":
                self.compress_video(video)
            print(audio_type["codec_name"])
    
    def ffprobe_video(self, video):
        # Call ffprobe
        try:
            ffprobe = run([
                "ffprobe", 
                "-show_format", 
                "-show_streams", 
                "-print_format", "json", 
                video
                ], shell=True, check=True, capture_output=True, text=True).stdout
        except CalledProcessError: 
            self.logger.error(f"Something went wrong while checking for Video codec on {video}, skipping")
            return False

        # Load it as json
        try:
            ffprobe = json.loads(ffprobe)['streams']
            return ffprobe
        except Exception as e:
            self.logger.error(f"{e} while trying to load ffprobe output as json")
            return False
    
    def compress_video(self, video):
        # Alright here is the place I will have to defend my settings:
        # JK just read this nice guide, I stole most of his settings
        # https://kokomins.wordpress.com/2019/10/10/anime-encoding-guide-for-x265-and-why-to-never-use-flac/ 
        # https://forum.videohelp.com/threads/398999-How-to-preserve-dark-lines-when-re-encoding-anime-to-x265

        # ffmpeg -i "[SubsPlease] Shingeki no Kyojin (The Final Season) - 70 (1080p) [78C16694].mkv" -c:v libx265 -crf 18 -x265-params limit-sao:bframes=8:psy-rd=1:aq-mode=3 -preset slow -c:a libopus try2.mkv

        # ffmpeg -i input.mp4 -c:v libx265 -vtag hvc1 output.mp4
        old_video_name = os.path.basename(video)
        
        # Rename the video
        #TODO improve the naming of the video
        try:
            new_video_name = str(old_video_name).split(".")[0]
            new_video_name = f"{new_video_name}.mkv"
        except Exception as e:
            self.logger.error(f"{video} does not have the correct file name, using defaults")
            new_video_name = datetime.now().strftime("%H:%M:%S")
            new_video_name = f"{new_video_name}.mkv"
        
        # Start the multithreading so we can have a loading screen
        t = threading.Thread(target=self.animate)
        t.start()
        
        try:  
            # I want a nice loading screen so you see its still working
            ffmpeg = run([
                "ffmpeg",
                "-i",
                os.path.normpath(video),
                "-c:v",
                "libx265",
                "-crf", "18",  # Changing this is the simplest higher -> more compression
                "-x265-params",
                "limit-sao:bframes=8:psy-rd=1:aq-mode=3",
                "-preset", "slow",
                "-c:a", 
                #"libopus", go opus for audio if you wannago the full open source meme
                "aac",
                f"{new_video_name}"
            ], shell=True, check=True, capture_output=True, text=True).stdout
            self.done_encoding = True
            # os.system('shutdown -s') # REMOVE
        except CalledProcessError as e:
            self.logger.debug(f"{e.output}")
            self.logger.error(f"Something went wrong while compressing {video}, skipping")
            self.done_encoding = True
            return False

    def animate(self):
        # Note the time
        start_time = datetime.now()
        run(["cls"], shell=True)
        for c in itertools.cycle(sprites()):
            if self.done_encoding:
                break
            time.sleep(10)
            run(["cls"], shell=True)
            # Get the amount of seconds passed since the first measurement
            elapsed_time = int((datetime.now() - start_time).total_seconds())
            print(f"\rUUUOOOOHHHH I'M LOADING ONII-CHAN \b Seconds taken: {elapsed_time} \b{c}", flush=True, end="")
        elapsed_time = int((datetime.now() - start_time).total_seconds())
        sys.stdout.write(f'\rDone encoding! \b took {elapsed_time} seconds')
    
                

if __name__ == '__main__':
    path = os.path.dirname(os.path.realpath(__file__))
    debug = True
    Encode(path, debug).encode_videos()