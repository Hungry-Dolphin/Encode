import os 
import logging as log 
from mimetypes import guess_type
from subprocess import run, CalledProcessError
import json
from datetime import datetime
from tracemalloc import start
from loading import sprites
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
            # If the file is actually a directory
            if os.path.isdir(os.path.join(path, file)):
                self.logger.info(f"{file} is a directory")
                # Get the path to this dir
                folder_path = os.path.join(path, file)
                # Call recursion to include all files in said directory
                self.discover_files(folder_path)
                continue
            
            # If the file is actually a file append its path to the list of files
            self.list_of_files.append(os.path.join(path, file))

    def get_video_files(self):
        # Iterate though all files
        for file in self.list_of_files:
            # Guess the type of file it is
            file_type = guess_type(file, strict=True)[0]
            
            if 'video' in file_type:
                # I could have just saved it as a list and checked what kind of encoding was used later
                # However I am not a fan of lists 
                try:
                    encoding = file_type.split("/")[1]
                    self.logger.debug(f"{file} is a video with {encoding} encoding")
                    self.all_video[f'{file}'] = encoding
                except IndexError:
                    self.logger.debug(f"Found a video which does not have the proper file type split") 
                    self.logger.error("\b Ignoring {file} with value {file_type}")


    def encode_videos(self):
        for video, encoding in self.all_video.items():
            self.logger.debug(f"Now working on {video}")

            # Call ffprobe for the video     
            try:
                ffprobe = self.ffprobe_video(video)
            except CalledProcessError:
                self.logger.error(f"ffprobe command execution not succesfull, skipping video \b {video}")
                continue
            except Exception as e:
                 self.logger.error(f"Error {e} for video {video} \b skipping video")
                 continue

            # In our case we only want to know the video and audio stream, any other streams are out of scope for now
            try:
                video_type = ffprobe[0]
                audio_type = ffprobe[1]
            except Exception as e:
                self.logger.error(f"Video {video} does not have 2 streams \b Did you download hardsubbed content?, skipping")
                continue

            print(audio_type["codec_name"])
            if video_type["codec_name"] != "h265":
                try:
                    current_video_name = self.compress_video(video)
                except CalledProcessError:
                    self.logger.error(f"Skipping {video} with {encoding} encoding")
                    continue

                new_video_path = self.clean_video_name(video, current_video_name)

                self.move_file(new_video_path, video)
            
        # os.system('shutdown -s') # REMOVE
    
    def move_file(self, ):
        print("")

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
            raise CalledProcessError

        # Load it as json
        try:
            ffprobe = json.loads(ffprobe)['streams']
            return ffprobe
        except Exception as e:
            self.logger.error(f"{e} while trying to load ffprobe output as json")
            return e
    
    def clean_video_name(self, old_video_path, current_video_name):
        # Get the name of the original video
        old_video_name = os.path.basename(old_video_path)

        # Rename the current video to something more appropriate
        #TODO improve the naming, for now ill just use the current name but this can cause conflicts when files have the same name
        new_video_name = str(old_video_name).split(".")[0]
        new_video_name = f"{new_video_name}.mkv"

    def compress_video(self, video):
        # Alright here is the place I will have to defend my settings:
        # JK just read this nice guide, I stole most of his settings
        # https://kokomins.wordpress.com/2019/10/10/anime-encoding-guide-for-x265-and-why-to-never-use-flac/ 
        # https://forum.videohelp.com/threads/398999-How-to-preserve-dark-lines-when-re-encoding-anime-to-x265

        # ffmpeg -i "in" -c:v libx265 -crf 18 -x265-params limit-sao:bframes=8:psy-rd=1:aq-mode=3 -preset slow -c:a libopus out.mkv

        # ffmpeg -i input.mp4 -c:v libx265 -vtag hvc1 output.mp4
        
        # Create a temporary name for the video
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
            
            # When successful return the filename of the just converted video
            return new_video_name

        except CalledProcessError as e:
            self.logger.debug(f"{e.output}")
            self.logger.error(f"Something went wrong while compressing {video}, skipping")
            raise CalledProcessError

    def animate(self):
        # Note the current time so we can tell how much time has passed
        start_time = datetime.now()
        run(["cls"], shell=True)
        #TODO find proper "art" to use
        for c in itertools.cycle(sprites()):
            if self.done_encoding:
                break
            time.sleep(10)
            run(["cls"], shell=True)
            # Get the amount of seconds passed since the first measurement
            elapsed_time = int((datetime.now() - start_time).total_seconds())
            print(f"\rEncoding \b Seconds taken: {elapsed_time} \b{c}", flush=True, end="")
        elapsed_time = int((datetime.now() - start_time).total_seconds())
        sys.stdout.write(f'\rDone encoding! \b took {elapsed_time} seconds')
    
                

if __name__ == '__main__':
    path = os.path.dirname(os.path.realpath(__file__))
    debug = True
    Encode(path, debug).encode_videos()