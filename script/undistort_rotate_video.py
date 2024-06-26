import argparse
import glob
import logging
import multiprocessing as mp
import os
import pathlib
import sys
import time
from functools import partial

import click
import cv2
import numpy as np
import psutil
from tqdm import tqdm

import br2_vision
from br2_vision.undistort import undistort
from br2_vision.utility.logging import config_logging, get_script_logger


def process_frame(frame, calibration_file, rotate):
    # Monitor memory usage
    # print(psutil.virtual_memory())

    # Undistort
    height, width = frame.shape[:2]
    frame = undistort(frame, width, height, calibration_file)

    # Rotate (Must be done after undistort)
    if rotate != None:
        frame = cv2.rotate(frame, rotate)

    return frame


@click.command()
@click.option(
    "-cam", "--cam-id", type=int, help="Camera index given in file.", multiple=True
)
@click.option(
    "-r",
    "--rotate",
    type=str,
    default=None,
    help="Rotation in cv2 (ex:ROTATE_90_CLOCKWISE)",
)
@click.option(
    "--output-fps",
    type=int,
    default=60,
    help="Output video FPS. Try to match the original video settings.",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose")
@click.option("-d", "--dry", is_flag=True, default=False, help="Dry run")
@click.option(
    "-p",
    "--processes",
    type=int,
    default=mp.cpu_count(),
    help="Max workers. (default: all cores)",
)
@click.option(
    "-cs",
    "--chunksize",
    type=int,
    default=1,
    help="Chunksize per core for multiprocessing. (default: 1)",
)
@click.option(
    "-o",
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing file. If False, skip existing file.",
)
def undistort_and_rotate(
    cam_id,
    rotate,
    output_fps,
    verbose,
    dry,
    processes,
    chunksize,
    overwrite,
):
    """
    Undistort and rotate the video.
    """

    config = br2_vision.load_config()
    config_logging(verbose)
    logger = get_script_logger(os.path.basename(__file__))

    logger.info(f"using {processes=} processes")

    calibration_file = config["PATHS"]["fisheye_configuration"]
    os.path.exists(calibration_file), f"calibration file not found: {calibration_file}"

    if rotate is not None:
        cv2_rotation = getattr(cv2, rotate, None)
    else:
        cv2_rotation = None

    for cid in cam_id:
        video_path = config["PATHS"]["raw_video_path"].format(cid)
        save_path = config["PATHS"]["undistorted_video_path"].format(cid)

        # if save_path axist, remove
        if os.path.exists(save_path):
            if overwrite:
                logger.info(f"file exist. overwriting on {save_path}")
                os.remove(save_path)
            else:
                logger.info(f"file exist. skipping {save_path}")
                continue

        if dry:
            continue

        # Create an object to read
        video = cv2.VideoCapture(video_path)

        # We need to check if camera
        # is opened previously or not
        if video.isOpened() == False:
            logger.info("Error reading video file {}".format(video_path))
            continue

        # We need to set resolutions.
        # so, convert them from float to integer.

        frame_width = int(video.get(3))
        frame_height = int(video.get(4))
        if (
            cv2_rotation is cv2.ROTATE_90_CLOCKWISE
            or cv2_rotation is cv2.ROTATE_90_COUNTERCLOCKWISE
        ):
            frame_width, frame_height = frame_height, frame_width
        size = (frame_width, frame_height)  # Make sure the size is upright
        logger.info(f"video size: {frame_width=}x{frame_height=}")

        # Below VideoWriter object will create
        # a frame of above defined The output
        output_writer = cv2.VideoWriter(
            save_path, cv2.VideoWriter_fourcc(*"mp4v"), output_fps, size
        )

        logger.info("writing video...")
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        pbar = tqdm(total=total_frames)

        pool = mp.Pool(processes=processes)
        stime = time.time()
        done_flag = False
        while not done_flag:
            chunk = []  # TODO: Try to collect frames in parallel
            for n in range(chunksize * processes):
                ret, frame = video.read()
                if not ret:
                    done_flag = True
                    break
                chunk.append(frame)
            if len(chunk) > 0:
                func = partial(
                    process_frame,
                    calibration_file=calibration_file,
                    rotate=cv2_rotation,
                )
                results = pool.map(func, chunk, chunksize=chunksize)
                pbar.update(len(results))

                # Write video
                shape = results[0].shape
                assert (
                    shape[0] == frame_height and shape[1] == frame_width
                ), f"shape={shape} != {frame_height}x{frame_width}x3"
                for frame in results:
                    # check nan
                    _frame = cv2.resize(frame, (frame_width, frame_height))
                    output_writer.write(_frame)

        # When everything done, release
        # the video capture and video
        # write objects
        video.release()
        output_writer.release()
        pbar.close()
        pool.close()

        logger.info("The video was successfully saved - {}".format(save_path))
        logger.info(f"took {time.time() - stime:.2f} seconds")
    logger.info("done")


if __name__ == "__main__":
    undistort_and_rotate()
