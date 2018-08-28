import datetime
import io
import os
import sys
import time
import zipfile
import requests

import azure.batch.batch_auth as batchauth
import azure.batch.batch_service_client as batch
import azure.batch.models as batchmodels
import azure.storage.blob as azureblob

# Update with your Batch and Storage Account credentials
_BATCH_ACCOUNT_NAME = ''
_BATCH_ACCOUNT_KEY = ''
_BATCH_ACCOUNT_URL = ''
_STORAGE_ACCOUNT_NAME = ''
_STORAGE_ACCOUNT_KEY = ''
_POOL_ID = 'IlastikDrosophilaSegmentation'
_DEDICATED_POOL_NODE_COUNT = 5
_POOL_VM_SIZE = 'STANDARD_A1_v2'
_JOB_ID = 'IlastikDrosophilaSegmentationJob'
_STANDARD_OUT_FILE_NAME = 'stdout.txt'

_DROSOPHILA_DSET_URL = "http://data.ilastik.org/drosophila.zip"
_DROSOPHILA_LOCAL_DIR = "drosophila_3d+t"
_ILASTIK_DOWNLOAD_URL = "http://files.ilastik.org/ilastik-1.3.0-Linux.tar.bz2"
# Drosophila dataset is a 5D tensor with the following axis order: txyzc
_DATASET_DIMS = (50, 300, 275, 50, 1)


def get_container_sas_token(block_blob_client,
                            container_name, blob_permissions):
    """
    Obtains a shared access signature granting the specified permissions to the
    container.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param str container_name: The name of the Azure Blob storage container.
    :param BlobPermissions blob_permissions:
    :rtype: str
    :return: A SAS token granting the specified permissions to the container.
    """
    # Obtain the SAS token for the container, setting the expiry time and
    # permissions. In this case, no start time is specified, so the shared
    # access signature becomes valid immediately. Expiration is in 2 hours.
    container_sas_token = \
        block_blob_client.generate_container_shared_access_signature(
            container_name,
            permission=blob_permissions,
            expiry=datetime.datetime.utcnow() + datetime.timedelta(hours=2))

    return container_sas_token


def upload_file_to_container(block_blob_client, container_name, file_path):
    """
    Uploads a local file to an Azure Blob storage container.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param str container_name: The name of the Azure Blob storage container.
    :param str file_path: The local path to the file.
    :rtype: `azure.batch.models.ResourceFile`
    :return: A ResourceFile initialized with a SAS URL appropriate for Batch
    tasks.
    """
    blob_name = os.path.basename(file_path)

    print('Uploading file {} to container [{}]...'.format(file_path,
                                                          container_name))

    block_blob_client.create_blob_from_path(container_name,
                                            blob_name,
                                            file_path)

    # Obtain the SAS token for the container.
    sas_token = get_container_sas_token(block_blob_client,
                                        container_name,
                                        azureblob.BlobPermissions.READ)

    sas_url = block_blob_client.make_blob_url(container_name,
                                              blob_name,
                                              sas_token=sas_token)

    return batchmodels.ResourceFile(file_path=blob_name,
                                    blob_source=sas_url)


def download_blobs_from_container(block_blob_client,
                                  container_name, directory_path):
    """
    Downloads all blobs from the specified Azure Blob storage container.
    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param container_name: The Azure Blob storage container from which to
     download files.
    :param directory_path: The local directory to which to download the files.
    """
    print('Downloading all files from container [{}]...'.format(
        container_name))

    container_blobs = block_blob_client.list_blobs(container_name)

    for blob in container_blobs.items:
        destination_file_path = os.path.join(directory_path, blob.name)

        block_blob_client.get_blob_to_path(container_name,
                                           blob.name,
                                           destination_file_path)

        print('  Downloaded blob [{}] from container [{}] to {}'.format(
            blob.name,
            container_name,
            destination_file_path))

    print('Download complete!')


def download_and_extract_dataset(skip_on_exists=True):
    """
    Downloads and extracts Drosophila dataset from the http://ilastik.org/download.html

    :param bool skip_on_exists: skip download if the target directory exits
    """

    if skip_on_exists and os.path.exists(_DROSOPHILA_LOCAL_DIR):
        print(
            "Dataset download skipped. '%s' already exists" % _DROSOPHILA_LOCAL_DIR)
        return

    print("Downloading and extracting %s ..." % _DROSOPHILA_DSET_URL)
    input_file_stream = io.BytesIO(requests.get(_DROSOPHILA_DSET_URL).content)
    z = zipfile.ZipFile(input_file_stream)
    z.extractall()


def get_container_sas_url(block_blob_client,
                          container_name, blob_permissions):
    """
    Obtains a shared access signature URL that provides write access to the
    ouput container to which the tasks will upload their output.

    :param block_blob_client: A blob service client.
    :type block_blob_client: `azure.storage.blob.BlockBlobService`
    :param str container_name: The name of the Azure Blob storage container.
    :param BlobPermissions blob_permissions:
    :rtype: str
    :return: A SAS URL granting the specified permissions to the container.
    """
    # Obtain the SAS token for the container.
    sas_token = get_container_sas_token(block_blob_client,
                                        container_name,
                                        azureblob.BlobPermissions.WRITE)

    # Construct SAS URL for the container
    container_sas_url = "https://{}.blob.core.windows.net/{}?{}".format(
        _STORAGE_ACCOUNT_NAME, container_name, sas_token)

    return container_sas_url


def create_pool(batch_service_client, pool_id):
    """
    Creates a pool of compute nodes with the specified OS settings.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str pool_id: An ID for the new pool.
    :param str publisher: Marketplace image publisher
    :param str offer: Marketplace image offer
    :param str sku: Marketplace image sky
    """
    print('Creating pool [{}]...'.format(pool_id))

    # The start task downloads and installs ilastik  on each node and cd
    # into the ilastik directory (which resides in the nodes shared directory)

    command_line = "/bin/bash -c \"wget {} -P $AZ_BATCH_NODE_SHARED_DIR && cd $AZ_BATCH_NODE_SHARED_DIR && tar xjf ilastik*.tar.bz2\"".format(
        _ILASTIK_DOWNLOAD_URL)

    new_pool = batch.models.PoolAddParameter(
        id=pool_id,
        virtual_machine_configuration=batchmodels.VirtualMachineConfiguration(
            image_reference=batchmodels.ImageReference(
                publisher="Canonical",
                offer="UbuntuServer",
                sku="16.04.0-LTS",
                version="latest"
            ),
            node_agent_sku_id="batch.node.ubuntu 16.04"),
        vm_size=_POOL_VM_SIZE,
        target_dedicated_nodes=_DEDICATED_POOL_NODE_COUNT,
        start_task=batchmodels.StartTask(
            command_line=command_line,
            wait_for_success=True,
            user_identity=batchmodels.UserIdentity(
                auto_user=batchmodels.AutoUserSpecification(
                    scope=batchmodels.AutoUserScope.pool,
                    elevation_level=batchmodels.ElevationLevel.admin)),
        )
    )
    batch_service_client.pool.add(new_pool)


def create_job(batch_service_client, job_id, pool_id):
    """
    Creates a job with the specified ID, associated with the specified pool.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The ID for the job.
    :param str pool_id: The ID for the pool.
    """
    print('Creating job [{}]...'.format(job_id))

    job = batch.models.JobAddParameter(
        job_id,
        batch.models.PoolInformation(pool_id=pool_id))

    batch_service_client.job.add(job)


def add_tasks(batch_service_client, job_id, project_file, input_dset,
              output_container_sas_url):
    """
    Adds a task for each time slice of the Drosophila dataset to the specified job.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The ID of the job to which to add the tasks.
    :param project_file: ilastik proejct file containing pre-trained model
    :param input_dset: Dataset to be concurrently processed by ilastik processes
    :param output_container_sas_token: A SAS token granting write access to
    the specified Azure Blob storage container.
    """

    # number of time slices
    t_slices = _DATASET_DIMS[0]
    print('Adding {} tasks to job [{}]...'.format(t_slices, job_id))

    tasks = []
    input_file_path = input_dset.file_path
    project_file_path = project_file.file_path
    export_source = "Simple Segmentation"
    output_format = "multipage tiff"
    export_dtype = "uint16"

    start_region = list((0, 0, 0, 0, 0))
    end_region = list(_DATASET_DIMS)

    for t in range(t_slices):
        output_file_path = "".join(input_file_path.split('.')[:-1]) + '_' + str(
            t) + '_seg.tiff'
        # create cutout subregion for the task
        start_region[0] = t
        end_region[0] = t + 1
        cutout_subregion = [tuple(start_region), tuple(end_region)]
        command = f"/bin/bash -c \"$AZ_BATCH_NODE_SHARED_DIR/ilastik-1.3.0-Linux/run_ilastik.sh --headless  --project={project_file_path}  --export_source='{export_source}' --output_format='{output_format}' --output_filename_format='{output_file_path}' --export_dtype='{export_dtype}' --cutout_subregion='{cutout_subregion}' {input_file_path}\""
        tasks.append(batch.models.TaskAddParameter(
            id='Task{}'.format(t),
            command_line=command,
            resource_files=[project_file, input_dset],
            output_files=
            [_create_output_file(output_container_sas_url, output_file_path)])
        )
    batch_service_client.task.add_collection(job_id, tasks)


def _create_output_file(output_container_sas_url, output_file_path):
    return batchmodels.OutputFile(
        output_file_path,
        destination=batchmodels.OutputFileDestination(
            container=batchmodels.OutputFileBlobContainerDestination(
                output_container_sas_url)),
        upload_options=batchmodels.OutputFileUploadOptions(
            batchmodels.OutputFileUploadCondition.task_success))


def wait_for_tasks_to_complete(batch_service_client, job_id, timeout):
    """
    Returns when all tasks in the specified job reach the Completed state.

    :param batch_service_client: A Batch service client.
    :type batch_service_client: `azure.batch.BatchServiceClient`
    :param str job_id: The id of the job whose tasks should be monitored.
    :param timedelta timeout: The duration to wait for task completion. If all
    tasks in the specified job do not reach Completed state within this time
    period, an exception will be raised.
    """
    timeout_expiration = datetime.datetime.now() + timeout

    print("Monitoring all tasks for 'Completed' state, timeout in {}..."
          .format(timeout), end='')

    while datetime.datetime.now() < timeout_expiration:
        print('.', end='')
        sys.stdout.flush()
        tasks = batch_service_client.task.list(job_id)

        incomplete_tasks = [task for task in tasks if
                            task.state != batchmodels.TaskState.completed]
        if not incomplete_tasks:
            print()
            return True
        else:
            time.sleep(1)

    print()
    raise RuntimeError("ERROR: Tasks did not reach 'Completed' state within "
                       "timeout period of " + str(timeout))


def print_task_output(batch_service_client, job_id, encoding=None):
    """Prints the stdout.txt file for each task in the job.

    :param batch_client: The batch client to use.
    :type batch_client: `batchserviceclient.BatchServiceClient`
    :param str job_id: The id of the job with task output files to print.
    """

    print('Printing task output...')

    tasks = batch_service_client.task.list(job_id)

    for task in tasks:
        node_id = batch_service_client.task.get(job_id,
                                                task.id).node_info.node_id
        print("Task: {}".format(task.id))
        print("Node: {}".format(node_id))

        stream = batch_service_client.file.get_from_task(job_id, task.id,
                                                         _STANDARD_OUT_FILE_NAME)

        file_text = _read_stream_as_string(
            stream,
            encoding)
        print("Standard output:")
        print(file_text)


def _read_stream_as_string(stream, encoding):
    """Read stream as string

    :param stream: input stream generator
    :param str encoding: The encoding of the file. The default is utf-8.
    :return: The file content.
    :rtype: str
    """
    output = io.BytesIO()
    try:
        for data in stream:
            output.write(data)
        if encoding is None:
            encoding = 'utf-8'
        return output.getvalue().decode(encoding)
    finally:
        output.close()
    raise RuntimeError('could not write data to stream or decode bytes')


if __name__ == '__main__':

    start_time = datetime.datetime.now().replace(microsecond=0)
    print('Sample start: {}'.format(start_time))
    print()

    # Create the blob client, for use in obtaining references to
    # blob storage containers and uploading files to containers.

    blob_client = azureblob.BlockBlobService(
        account_name=_STORAGE_ACCOUNT_NAME,
        account_key=_STORAGE_ACCOUNT_KEY)

    # Use the blob client to create the containers in Azure Storage if they
    # don't yet exist.

    input_container_name = 'drosophiladataset'
    output_container_name = 'drosophilasegmentation'
    blob_client.create_container(input_container_name, fail_on_exist=False)
    blob_client.create_container(output_container_name, fail_on_exist=False)
    print('Container [{}] created.'.format(input_container_name))
    print('Container [{}] created.'.format(output_container_name))

    # Download and extract the dataset
    download_and_extract_dataset()

    input_file_paths = [
        os.path.relpath(os.path.join(_DROSOPHILA_LOCAL_DIR, f_name))
        for f_name in ["drosophila_00-49.h5", "pixelClassification.ilp"]]

    # Upload ilastik project file containing trained pixel classification model
    # and the Drosophila dataset file
    input_dset, project_file = [
        upload_file_to_container(blob_client, input_container_name, file_path)
        for file_path in input_file_paths]

    # Obtain a shared access signature URL that provides write access to the output
    # container to which the tasks will upload their output.

    output_container_sas_url = get_container_sas_url(
        blob_client,
        output_container_name,
        azureblob.BlobPermissions.WRITE)

    # Create a Batch service client. We'll now be interacting with the Batch
    # service in addition to Storage
    credentials = batchauth.SharedKeyCredentials(_BATCH_ACCOUNT_NAME,
                                                 _BATCH_ACCOUNT_KEY)

    batch_client = batch.BatchServiceClient(
        credentials,
        base_url=_BATCH_ACCOUNT_URL)

    try:
        # Create the pool that will contain the compute nodes that will execute
        # the tasks.
        create_pool(batch_client, _POOL_ID)

        # Create the job that will run the tasks.
        create_job(batch_client, _JOB_ID, _POOL_ID)

        # Add the tasks to the job. Pass the input files and a SAS URL
        # to the storage container for output files.
        add_tasks(batch_client, _JOB_ID, project_file, input_dset,
                  output_container_sas_url)

        # Pause execution until tasks reach Completed state.
        wait_for_tasks_to_complete(batch_client,
                                   _JOB_ID,
                                   datetime.timedelta(minutes=30))

        print(
            "Job finished! Downloading all blobs from the output container...")
        download_blobs_from_container(blob_client, output_container_name, '.')

        # Print the stdout.txt files for each task to the console
        print_task_output(batch_client, _JOB_ID)

    except batchmodels.batch_error.BatchErrorException as err:
        print('Exception encountered:', repr(err))
        raise

    # Cleanup (comment below lines if you want to keep your job/pool/container

    # Delete input container in storage, but keep the output container with the output segmentation
    print(f'Deleting container [{input_container_name}]...')
    blob_client.delete_container(input_container_name)
    # Delete job
    print(f'Deleting job [{_JOB_ID}]...')
    batch_client.job.delete(_JOB_ID)
    # Delete pool
    print(f'Deleting pool [{_POOL_ID}]...')
    batch_client.pool.delete(_POOL_ID)

    # Print out timing info
    end_time = datetime.datetime.now().replace(microsecond=0)
    print()
    print('Sample end: {}'.format(end_time))
    print('Elapsed time: {}'.format(end_time - start_time))
    print()
