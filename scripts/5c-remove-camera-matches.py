#!/usr/bin/python3

# remove all match references to a specific image ... can be used as a
# blunt hammer when something is going wrong with that image

import argparse
import pickle
import os

import sys
sys.path.append('../lib')
import ProjectMgr

import match_culling as cull

parser = argparse.ArgumentParser(description='Remove all matches referencing the specific image.')
parser.add_argument('--project', required=True, help='project directory')
parser.add_argument('--area', required=True, help='sub area directory')
parser.add_argument('--index', type=int, help='image index')
parser.add_argument('--images', nargs='+', help='image names')
args = parser.parse_args()

proj = ProjectMgr.ProjectMgr(args.project)
proj.load_area_info(args.area)

area_dir = os.path.join(args.project, args.area)

print("Loading matches_grouped...")
matches_grouped = pickle.load( open( os.path.join(area_dir, "matches_grouped"), "rb" ) )
print("  features:", len(matches_grouped))

print("Loading matches_opt...")
matches_opt = pickle.load( open( os.path.join(area_dir, "matches_opt"), "rb" ) )
print('  features:', len(matches_opt))

def remove_image_features(index, matches):
    # iterate through the match dictionary and mark any matches for
    # the specified image for deletion
    print("Marking feature matches for image:", index)
    count = 0
    for i, match in enumerate(matches):
        for j, p in enumerate(match[2:]):
            if p[0] == index:
                cull.mark_feature(matches, i, j, 0)
                count += 1
    return count

index = None
count_grouped = 0
count_opt = 0
if not args.images is None:
    for name in args.images:
        index = proj.findIndexByName(name)
        if index == None:
            print("Cannot locate by name:", args.images)
        else:
            count_grouped += remove_image_features(index, matches_grouped)
            count_opt += remove_image_features(index, matches_opt)
elif args.index:
    if args.index >= len(proj.image_list):
        print("Index greater than image list size:", args.index)
    else:
        index = args.index
        count_grouped = remove_image_features(index, matches_grouped)
        count_opt = remove_image_features(index, matches_opt)
    
if count_grouped + count_opt > 0:
    print('Features marked:', count_grouped, count_opt)
    result = input('Delete these matches and save? (y/n):')
    if result == 'y' or result == 'Y':
        cull.delete_marked_features(matches_grouped)
        cull.delete_marked_features(matches_opt)
        
        # write out the updated match dictionaries
        print("Writing: matches_grouped")
        pickle.dump(matches_grouped, open(os.path.join(area_dir, "matches_grouped"), "wb"))
        print("Writing matches_opt")
        pickle.dump(matches_opt, open(os.path.join(area_dir, "matches_opt"), "wb"))

