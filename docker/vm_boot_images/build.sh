#!/usr/bin/env bash

# This script can be used to build and tag a 'ml4h' image, optionally push it to Google Container Registry,
# and again optionally, tag the image also as 'latest_<gpu|cpu>'.
#
# It assumes 'gcloud' has been installed, Docker has been configured to use 'gcloud' as a credential helper
# by running 'gcloud auth configure-docker', and the script is being run at the root of the GitHub repo clone.

# Stop the execution if any of the commands fails
set -e

################### VARIABLES ############################################

REPO="gcr.io/broad-ml4cvd/deeplearning"
GITHUB_REPO="ghcr.io/broadinstitute/ml4h"
TAG=$( git rev-parse --short HEAD )
CONTEXT="docker/vm_boot_images/"
CPU_ONLY="false"
PUSH_TO_GCR="false"
PUSH_TO_LATEST="false"

BASE_IMAGE_GPU="tensorflow/tensorflow:2.19.0-gpu"
BASE_IMAGE_CPU="tensorflow/tensorflow:2.19.0"

LATEST_TAG_GPU="tf2.19-latest-gpu"
LATEST_TAG_CPU="tf2.19-latest-cpu"

SCRIPT_NAME=$( echo $0 | sed 's#.*/##g' )

RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No colour

################### HELPER FUNCTIONS ############################################

usage()
{
    cat <<USAGE_MESSAGE

    This script can be used to build and tag a 'ml4h' image, optionally push it to Google Container Registry,
    and again optionally, tag the image also as 'latest_<gpu|cpu>'.

    It assumes 'gcloud' has been installed, Docker has been configured to use 'gcloud' as a credential helper
    by running 'gcloud auth configure-docker', and the script is being run at the root of the GitHub repo clone.

    Usage: ${SCRIPT_NAME} [-d <path>] [-t <tag>] [-chp]

    Example: ./${SCRIPT_NAME} -d /Users/kyuksel/github/ml4h/jamesp/docker/deeplearning -cp

        -d      <path>      Path to directory where Dockerfile is located. Default: '${CONTEXT}'

        -t      <tag>       String used to tag the Docker image. Default: short version of the latest commit hash

        -c                  Build off of the cpu-only base image and tag image also as '${LATEST_TAG_CPU}'.
                            Default: Build image to run on GPU-enabled machines and tag image also as '${LATEST_TAG_GPU}'.

        -p                  Push to Google Container Register
        -P                  Push to latest tag and to the Github GHCR repository

        -h                  Print this help text

USAGE_MESSAGE
}

################### OPTION PARSING #######################################

while getopts ":d:t:chpP" opt ; do
    case ${opt} in
        h)
            usage
            exit 1
            ;;
        d)
            CONTEXT=$OPTARG
            ;;
        t)
            TAG=$OPTARG
            ;;
        c)
            CPU_ONLY="true"
            ;;
        p)
            PUSH_TO_GCR="true"
            ;;
        P)
            PUSH_TO_LATEST="true"
            ;;
        :)
            echo -e "${RED}ERROR: Option -${OPTARG} requires an argument.${NC}" 1>&2
            usage
            exit 1
            ;;
        *)
            echo -e  "${RED}ERROR: Invalid option: -${OPTARG}${NC}" 1>&2
            usage
            exit 1
            ;;
    esac
done
shift $((OPTIND - 1))

################### SCRIPT BODY ##########################################

echo CPU_ONLY $CPU_ONLY
if [[ ${CPU_ONLY} == "true" ]]; then
    BASE_IMAGE=${BASE_IMAGE_CPU}
    LATEST_TAG=${LATEST_TAG_CPU}
    TAG=${TAG}-cpu
else
    BASE_IMAGE=${BASE_IMAGE_GPU}
    LATEST_TAG=${LATEST_TAG_GPU}
    TAG=${TAG}-gpu
fi

echo BASE_IMAGE $BASE_IMAGE LATEST_TAG $LATEST_TAG
echo -e "${BLUE}Building Docker image '${REPO}:${TAG}' from base image '${BASE_IMAGE}', and also tagging it as '${LATEST_TAG}'...${NC}"
# --network host allows for the container's network stack to use the Docker host's network
docker build ${CONTEXT} \
    --build-arg BASE_IMAGE=${BASE_IMAGE} \
    --tag "${REPO}:${TAG}" \
    --tag "${REPO}:${LATEST_TAG}" \
    --tag "${GITHUB_REPO}:${TAG}" \
    --tag "${GITHUB_REPO}:${LATEST_TAG}" \
    --network host \

echo PUSH_TO_LATEST $PUSH_TO_LATEST
if [[ ${PUSH_TO_LATEST} == "true" ]]; then
    echo -e "${BLUE}Pushing the image '${REPO}' to Github GHCR and Google Container Registry with tags '${TAG}' and '${LATEST_TAG}'...${NC}"
    docker push ${REPO}:${TAG}
    docker push ${REPO}:${LATEST_TAG}

    docker push ${GITHUB_REPO}:${TAG}
    docker push ${GITHUB_REPO}:${LATEST_TAG}
fi

echo PUSH_TO_GCR $PUSH_TO_GCR
if [[ ${PUSH_TO_GCR} == "true" ]]; then
    echo -e "${BLUE}Pushing the image '${REPO}' to Google Container Registry with tags '${TAG}'...${NC}"
    docker push ${REPO}:${TAG}
fi
