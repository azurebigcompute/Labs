# CycleCloud Specialized Compute (HPC) Lab
* Microsoft Specialized Compute (HPC) Team - <mailto:askcyclecloud @ microsoft.com>
* Initial versions by Rob Futrick, December 2017

## 1. Introduction

### 1.1  The Lab
This is a technical lab to help you get started using CycleCloud to create, use, and manage Big Compute/HPC/Big Data environments in Azure. In this lab, you will:
* setup and install CycleCloud on a VM
* configure CycleCloud to use Azure credentials
* create a simple HPC cluster consisting of a job scheduler and an NFS file server
* submit jobs and observe the cluster autoscale up and down automatically
* review CycleCloud's cost reporting & controls, reporting, and other features

Resources can be located at the end of the Lab, as well as links for more advanced topics. This Lab should take approximately 60-120 minutes to complete.

We welcome any thoughts or feedback. We are always looking for ways to improve the experience of learning CycleCloud!

### 1.2  CycleCloud

CycleCloud provides a simple, secure, and scalable way to manage compute and storage resources for HPC and Big Compute/Data workloads in Microsoft Azure. CycleCloud enables users to create environments for workloads on any point of the parallel and distributed processing spectrum, from parallel workloads to tightly-coupled applications such as MPI jobs on Infiniband/RDMA. By managing resource provisioning, configuration, and monitoring, CycleCloud allows users and IT staff to focus on business needs instead infrastructure.

CycleCloud delivers:

* Complete control over compute environments, including VM resources, storage, networking, and the full application stack
* Data transfer and management tools
* Role-based access control (RBAC)
* Templated applications and reference architectures
* Cost reporting and controls
* Monitoring and alerting
* Automated, customizable configuration
* Consistent security and encryption

If this is your first time using CycleCloud, we recommend reading the [CycleCloud User Guide](https://docs.cyclecomputing.com/user-guide-launch) to get more familiar with common CycleCloud concepts: clusters, nodes and node arrays, data management, etc. CycleCloud is a packaged, licensed application. For licensing and support options, or other general questions, email askcyclecloud @ microsoft.com.


## 2. Prerequisites
This lab has a few prerequisites to ensure you ready and able to perform the instructions.

1. Azure subscription ID

2. The [Azure CLI 2.0](https://docs.microsoft.com/en-us/cli/azure/overview?view=azure-cli-latest) installed and configured with an Azure subscription

3. A [service principal](https://docs.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli?view=azure-cli-latest) in your Azure Active Directory

4. An SSH keypair, for use when logging into the VMs created during the lab.

If you need to retrieve your Azure subscription ID, the following command will list all available IDs:
```
        $ az account list -o table
```

If you don't have a service principal available, you can create one using this example. Be sure to substitute the appropriate name and duration if you use it. Note that the service principal **name must be unique**.

```
        $ az ad sp create-for-rbac --name CcIntroTraining --years 1
```
        
This will output the following. Save the **appId**, **password**, and **tenant ID**. 
```
        {
                "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "displayName": "CcIntroTraining",
                "name": "http://CcIntroTraining",
                "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        }
```

## 3. Install & Setup

This lab uses an [Azure Resource Manager template](https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-authoring-templates) to:
1. Create the VM for CycleCloud, and to install CycleCloud on that VM
2. Create and configure the network for the CycleCloud environment
3. Create a bastion host for enabling more secure access to the CycleCloud instance

If you would like to learn more about installing CycleCloud directly, we recommend you read the [CycleCloud Installation Guide](https://docs.cyclecomputing.com/installation-guide-launch)


### 3.1 Customize ARM Template Files

Start by cloning the repo or otherwise downloading the files:  

    git clone https://github.com/azurebigcompute/BigComputeLabs.git

Change the directory to the Cycle Cloud lab:
 
    cd BigComputeLabs/CycleCloud

Three parameters in the vms-params.json file are of particular importance:

* `cycleDownloadUri` is the location of the CycleCloud installer for this lab
* `cycleLicenseURL` is the URL for the license to use for this lab
* `rsaPublicKey` is the SSH public key corresponding to the private key you will use to log into the VMs

Edit the vms-params.json file to specify the `rsaPublicKey` parameter. The `cycleDownloadUri` and `cycleLicenseSas` parameters have been pre-configured.

* `rsaPublicKey` = [Create](https://git-scm.com/book/en/v2/Git-on-the-Server-Generating-Your-SSH-Public-Key) your own keypair

### 3.2 Create Resource Group and Storage Account

Create a resource group in the region of your choice. Note that resource group names are unique within a subscription:

    az group create --name "{RESOURCE-GROUP}" --location "{REGION}"

For example, you could use "CycleCloudIntroTraining" as the resource group name and western Europe as the region:

    az group create --name "CycleCloudIntroTraining" --location "West Europe"

Create a storage account in the region of your choice.  

    az storage account create --name "{STORAGE-NAME}" --group "{RESOURCE-GROUP}" --location "{REGION}" --sku "Standard_LRS"

For example, you could use "CycleCloudStorageAccount" as the storage name and western Europe as the region:

    az storage account create --name "CycleCloudStorageAccount" --group "CycleCloudIntroTraining" --location "West Europe" --sku "Standard_LRS"
    
### 3.3 Setup Networking

Build the Virtual Network and subnets. By default, the vnet is named **cyclevnet**:

    az group deployment create --name "vnet_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/deploy-vnet.json --parameters vnet-params.json

For example:

    az group deployment create --name "vnet_deployment" --resource-group "CycleCloudIntroTraining" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/deploy-vnet.json --parameters vnet-params.json

### 3.4 Build VMs

Build the Virtual Machines:

    az group deployment create --name "vms_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/deploy-vms.json --parameters vms-params.json

For example:

    az group deployment create --name "vms_deployment" --resource-group "CycleCloudIntroTraining" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/deploy-vms.json --parameters vms-params.json


## 4. Configure CycleCloud Server

### 4.1 Initial Setup
To connect to the CycleCloud webserver, retrieve the FQDN of the CycleServer VM from the Azure Portal, then browse to https://cycleserverfqdn/. The installation uses a self-signed SSL certificate, which may show up with a warning in your browser.

When you first log into the CycleCloud webserver, the wizard will prompt for a Cycle Computing account. If you do not have an account, ignore the prompt, and click on **Next**.

![Account Setup](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/setup-step1.png)

Follow the steps to accept the CycleCloud license agreement and to create the local CycleCloud administrator account. Once the initial configuration wizard completes, a notice will appear that you currently do not have a cloud provider set up.

## 4.2 Add Azure Credentials
In this section, we'll configure CycleCloud to use your desired Azure subscription. CycleCloud needs valid Azure credentials in order to provision and orchestrate infrastructure on your behalf.

![Add CSP](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/no_accounts_found.png)

Click the link to add your subscription.

![Configure Subscription](https://docs.cyclecomputing.com/wp-content/uploads/2017/10/create_azure.png)

If not already set, select Microsoft Azure as the provider from the drop down. Enter the **Subscription ID**, **Tenant ID**, **Application ID**, and **Application Secret**. If you do not have these, look at the **Pre-requisites** section above for instructions on how to retrieve them. The service principal password is the **Application Secret**.

    Note: If the four values are set correctly, the **Default Location** will auto-populate with all of the available locations for your subscription. If the drop down is not autopopulating, double check the four values above.

Add the Storage Account and Storage Container to use for storing configuration and application data for your cluster. If it does not already exist, the container will be created.

Check the “Set Default” option to make this azure subscription the default. Once you have completed setting the parameters for your Azure account, click **Save** to continue.

For more detailed instructions, see the [Installation Guide](https://docs.cyclecomputing.com/installation-guide-v6.7.0/configuring_cloud_provider/masetup).


## 5. Create a Simple HPC Cluster (GUI)

Click on "Clusters" in the main menu. This will bring up the list of "cluster types" that are available. These are "easy buttons" for clusters, and expose a limited number of parameters in order to simplify and standardize cluster creation.

![New Clusters](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20Cluster.png)

Note that these are not the only types of clusters available. CycleCloud ships with a limited number of supported cluster types by default, but others are maintained in a central repository annd can easily be imported into CycleCloud. For more details, see the [CycleCloud Admin Guide](https://docs.cyclecomputing.com/administrator-guide-v6.7.0/template_customization).

Adding new cluster types and customizing existing cluster types will be covered in a separate lab.

### 5.1 Creating a Grid Engine Cluster

[Open Grid Scheduler](http://gridscheduler.sourceforge.net/) (OGS) is the open source version of the Sun Grid Engine job scheduler. To create an HPC cluster that is configured with the OGS scheduler, click on "Grid Engine".

![Grid Engine Cluster](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20Cluster.png)

This will bring up the cluster creation wizard.   

#### General Settings

In general, cluster creation wizards present the mandatory parameters on the first page/tab. Subsequent pages/tabs contain options for advanced customization. For this page, specify the cluster name and the region. The provider and credentials should be set correctly already.

When done, either click directly on "Cluster Software" in the left column, or click on the "Next" button in the lower right corner.

![General Settings](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20GE%20Cluster%20-%20General%20Settings.png)

#### Cluster Software

The Cluster Software tab presents two important parameters:
1. The "cluster-init" to use to customize the node configurations and installed software stack(s)
2. The ssh key used to enable direct ssh access to the cluster nodes

For this example, we will use a standard Grid Engine cluster and ssh key created by the ARM script. Leave all fields as is.

![Cluster Software](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20GE%20Cluster%20-%20Cluster%20Software.png)

#### Compute Backend

The "Compute Backend" tab allows users to:
    1. Customize the type of infrastructure used in the HPC cluster
    2. Control the autoscaling behavior of the cluster, which is *enabled by default*

![Compute Backend](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20GE%20Cluster%20-%20Compute%20Backend.png)

#### Networking

On this tab, select the "cyclevnet-compute" subnet. This will place the compute infrastructure into the correct subnet created by the ARM template. All other options can be ignored for this cluster.

![Networking](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20GE%20Cluster%20-%20Networking.png)

#### Saving the Cluster

At any point after specifying the cluster name and region, the new cluster can be "saved".

### 5.2 Setting a Usage/Cost Alert

Before starting the cluster, we can set an alert to let us know if the accumulated usage cost has reached a specified threshold. Create the alert by clicking on "Create new alert" in the cluster's summary window. This will bring up a dialog box.

For this example, we've set the alert to $100. Set the recipient to be your email address:  

![CostAlert](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20Cluster%20-%20Cluster%20Usage%20Alert.png)


### 5.3 Starting the Cluster

Start the cluster by clicking on the "Start" link underneath the cluster's name in the cluster summary window. 
 
![ClusterStartLink](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20Cluster%20Start%20Link.png)

Once the cluster is started, it will take several minutes to provision and orchestrate the VM for the cluster's master node as well as install and configure the Grid Engine job queue and scheduler. Progress can be monitored in the cluster VM details tab, as well as in the event log.
 
![ClusterStarted](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20New%20Cluster%20-%20Cluster%20Started.png)
 

## 6. Running Jobs on the HPC Cluster

In order to run jobs on the standard Grid Engine cluster, users need to log onto the cluster's "Master" node, where the Grid Engine job queue resides.

To connect to that VM, there are two options:
1. Connect using the CycleCloud CLI, which is installed on the CycleCloud VM, or
2. SSH using the private key, "cyclecloud.pem", specified during the cluster creation

In this example, we'll walk through how to connect using the CycleCloud CLI installed on the CycleCloud VM.

### 6.1 Connecting to the CycleCloud VM

For security reasons, the CycleCloud VM (CycleServer) is behind a jump box/bastion host. To access CycleServer, we must first log onto the jump box, and then ssh onto the CS instance. To do this, we'll add a second host to jump through to the ssh commands. For more information, see [this article](https://wiki.gentoo.org/wiki/SSH_jump_host).

In the Azure portal, retrieve the full DNS name of the admin jump box. You can then ssh to it with the **cycleadmin** user using the SSH key provided during the pre-requisite section. Please note that this is *not* the "cyclecloud.pem" file.

    $ ssh -J cycleadmin@{JUMPBOX PUBLIC HOSTNAME} cycleadmin@cycleserver -i {SSH PRIVATE KEY}

Here's an example command:

    $ ssh -J cycleadmin@adminjbmpiuvl.westeurope.cloudapp.azure.com cycleadmin@cycleserver -i .ssh/cyclecloud-training.pem

## 6.2 Setup CycleCloud CLI

Once on the CycleCloud VM, we'll need to initialize the CycleCloud CLI. First, change to the root user:

    [cycleadmin@cycleserver ~]$ sudo su -

Then, as the root user, initialize the CycleCloud CLI:

    [root@cycleserver ~]$ cyclecloud initialize
    CycleServer URL: [http://localhost:8080] https://localhost:443
    Detected untrusted certificate. Allow? [no] yes
    ...

Note: supply the admin username and password specified when creating the initial CycleCloud user account. The CycleServer URL is the FQDN of the cycleserver, for example https://cycleserver63i64inm.westeurope.cloudapp.azure.com

    CycleServer username: [root] ...
    CycleServer password:...
    Generating CycleServer key...
    Initial account already exists, skipping initial account creation.
    CycleCloud configuration stored in /root/.cycle/config.ini
    Wrote cluster template file '~/.cycle/condor_template.txt'.
    Wrote cluster template file '~/.cycle/kafka.txt'.
    Wrote cluster template file '~/.cycle/pbspro_template.txt'.
    Wrote cluster template file '~/.cycle/redis-cluster.txt'.
    Wrote cluster template file '~/.cycle/sge_template.txt'.
    Wrote cluster template file '~/.cycle/zookeeper.txt'.
    [root@cycleserver ~]#

### 6.3 Connecting to the Grid Engine Master

Once the CLI is initialized, we can use it to connect to the master node. In the CycleCloud GUI, click on "connect" to get the connection information. The connection string should be similar to the following, but with your cluster name substituted:

    [root@cycleserver ~]$ cyclecloud connect master -c cc-intro-training

![ClusterConnect](images/CC%20-%20Connect%20button.png)

Executing that command should produce:

    Connecting to cyclecloud@13.95.214.81 (instance ID: 1955d153a31f8996c04c9565c1540157) using SSH
    Last login: Mon Jan 22 16:25:45 2018 from 52.178.78.14
     __        __  |    ___       __  |    __         __|
    (___ (__| (___ |_, (__/_     (___ |_, (__) (__(_ (__|
            |
    Cluster: cc-intro-training
    Version: 6.7.0
    Run List: recipe[cyclecloud], role[sge_master_role], recipe[cluster_init]
    [cyclecloud@ip-0A000404 ~]$

Now you're logged onto the Grid Engine master node.

### 6.4 Submitting Jobs

Once on the master, check the status of the job queue by running the following commands:

    $ qstat
    $ qstat -f

The output will confirm that no jobs are running and no execute nodes are provisioned.

    queuename                      qtype resv/used/tot. load_avg arch          states
    ---------------------------------------------------------------------------------
    all.q@ip-0A000404              BIP   0/0/8          0.46     linux-x64

Execute the following command to submit 100 test "hostname" jobs. This will trigger CycleCloud's autoscale to add instances to the cluster, and CycleClouds automation will ensure they are added correctly then execute the jobs:

    [cyclecloud@ip-0A000404 ~]$ qsub -t 1:100 -V -b y -cwd hostname
    Your job-array 1.1-100:1 ("hostname") has been submitted

Confirm the jobs are in the queue by running the qstat command again:

    [cyclecloud@ip-0A000404 ~]$ qstat
    job-ID  prior   name       user         state submit/start at     queue                          slots ja-task-ID
    -----------------------------------------------------------------------------------------------------------------
          1 0.56000 hostname   cyclecloud   qw    01/22/2018 16:59:53                                    1 1-100:1
    [cyclecloud@ip-0A000404 ~]$    


### 6.5 Autoscaling Up & Down

At this point, no execute nodes have been provisioned, because the cluster is configured to autoscale. The cluster will detect that the job queue has work in it, and will provision compute nodes to execute the jobs. By default, the system will try to provision a core of compute power for every job, although this can be changed easily. Since there are 100 jobs, it will request 100 cores - but the cluster has a scale limit of 16 in place, so no more than 16 cores will be provisioned.

![Autoscaling](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20Cluster%20Autoscaling.png)

When the jobs are complete and the nodes are idle, they will scale down as well.

For a more in-depth discussion of CycleCloud's autoscaling behavior, plugins, and API, see the [admin guide](https://docs.cyclecomputing.com/administrator-guide-v6.7.0/autoscale_api).


## 7. Terminating the Cluster

When we no longer need the cluster, click "Terminate" to shutdown all of the infrastructure. Note that all underlying Azure resources will be cleaned up as part of the cluster termination. The operation may take several minutes.

![ClusterTermination](https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud/images/CC%20-%20Cluster%20Termination.png)


# End of the Lab
## Cleanup Resources
To clean up the resources allocated during the lab, simply delete the resource group. All resources within that group will be cleaned up as part of removing the group.

    az group delete --name "{RESOURCE-GROUP}"

Using our examples above:

    az group delete --name "CycleCloudIntroTraining" 

If desired, the service principal can also be deleted. Remember to use the service principal name used at the beginning of the lab.

    az ad sp delete --name "CycleCloudIntroTraining"
