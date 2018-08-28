Sample script for processing the 5D tensor containing the stack of Drosophila embryo in parallel with [ilasitk](http://ilastik.org/) running on Azure Batch via Python API. The app uploads the stack into a single storage container and then segments the nuclei via a parallel workload running 50 ilastik processes (there are 50 time points in the stack, it's one segmentation task per time point) in a headless mode (see http://ilastik.org/documentation/basics/headless from more information). The output of each segmentation task (one tiff file per time point containing segmented 3D stack) is uploaded to a single storage container and then downloaded into the current working dir. 

## Prerequisites
* python 3.6
* pip3

## Run the app
* Install virtualenv `pip3 install virtualenv`
* Go into the `python` dir and create virtual env for the app `cd python && python3 -m virtualenv env`
* Install required packages: `pip install -r requirements.txt`
* Update the Batch and storage account credentials inside the `ilasik_azure_batch_client.py`
* Run the script: `python ilasik_azure_batch_client.py`
* Wait for the script to finish and check that the output segmentation files have been successfully downloaded into your current directory (the files should be named `drosophila_00-49_{t}_seg.tiff`, where `t` corresponds to a given time point in the stack).

## Sample segmentation output
Output of the ilastik segmentation task for a sample time point:

![drosophila_00-49_25_segmentation](https://user-images.githubusercontent.com/706781/39076370-2bf13fe2-44fb-11e8-82c8-a99aa68f8b24.gif)
