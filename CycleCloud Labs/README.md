# CycleCloud Specialized Compute (HPC) Lab
* Microsoft Specialized Compute (HPC) Team - <mailto:askcyclecloud @ microsoft.com>
* Initial versions by Rob Futrick, December 2017

## 1. Introduction

### 1.1  The Lab
This is a technical lab to help you get started using CycleCloud to create, use, and manage Big Compute/HPC/Big Data environments in Azure. In this lab, you will:
* setup and install CycleCloud on a VM, 
* configure CycleCloud to use Azure credentials,
* create a simple HPC cluster consisting of a job scheduler and an NFS file server,
* submit jobs and observe the cluster autoscale up and down automatically,
* review CycleCloud's cost reporting & controls, reporting, and other features 

Included are locations and methods for getting more information or for learning more advanced topics. The Lab should take approx 60-120 minutes to complete.

We welcome any thoughts or feedback. We are always looking for ways to improve the experience of learning how to use CycleCloud!

### 1.2  CycleCloud

CycleCloud provides a simple, secure, and scalable way to manage compute and storage resources for HPC and Big Compute/Data workloads in Microsoft Azure Cloud. CycleCloud enables users to create environments for workloads on any point of the parallel and distributed processing spectrum, from pleasantly parallel workloads to tightly-coupled applications such as MPI jobs on Infiniband/RDMA. And by managing resource provisioning, configuration, and monitoring, CycleCloud allows users and IT staff to focus on business needs instead infrastructure. 

CycleCloud delivers:

* Complete control over compute environments, including VM resources, storage, networking, and the full application stack 
* Data transfer and management tools
* RBAC-based access control
* Templated applications and reference architectures
* Cost reporting and controls
* Monitoring and alerting
* Automated, customizable configuration
* Consistent security and encryption

If this is your first time using CycleCloud, we recommend reading the [CycleCloud User Guide](https://docs.cyclecomputing.com/user-guide-launch) to get more familiar with common CycleCloud's concepts: clusters, nodes and node arrays, data management, etc. CycleCloud is a packaged, licensed application. For licensing and support options, or other general questions, email askcyclecloud @ microsoft.com. 


## 2. Prerequisites
This lab has a few prerequisites to ensure you ready and able to perform the instructions. 

1. Azure subscription ID. 

2. The [Azure CLI 2.0](https://docs.microsoft.com/en-us/cli/azure/overview?view=azure-cli-latest) installed and configured with an Azure subscription

3. A [service principal](https://docs.microsoft.com/en-us/cli/azure/create-an-azure-service-principal-azure-cli?view=azure-cli-latest) in your Azure Active Directory

4. An SSH keypair, for use when logging into the VMs created during the lab.

If you need to retrieve your Azure subscription ID, the following command will list all available:
```
        $ az account list -o table
```

If you don't have a service principal available, you can create one. Here is an example, although substitute in the appropriate name and duration if you use it. Note that the service principal **name must be unique**.

Save the output of the create command. You'll need the **appId**, **password**, and **tenant ID**.
```
        $ az ad sp create-for-rbac --name CcIntroTraining --years 1
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
1. Create the VM for CycleCloud, and to install CycleCloud on that VM,
2. Create and configure the network for the CycleCloud environment,
3. Create a bastion host for enabling more secure access to the CycleCloud instance.

If you would like to learn more about installing CycleCloud directly, we recommend you read the [CycleCloud Installation Guide](https://docs.cyclecomputing.com/installation-guide-launch)


### 3.1 Customize ARM Template Files

Start by cloning the repo or otherwise downloading the files.  

    git clone https://github.com/azurebigcompute/Labs.git

Edit the vms-params.json file. You need to update three parameters: `cycleDownloadUri`, `cycleLicenseSas`, and `rsaPublicKey`

* `cycleDownloadUri` is the location of the CycleCloud installer for this lab.
* `cycleLicenseSas` is the license to use for this lab. 
* `rsaPublicKey` is the SSH public key corresponding to the private key you will use to log into the VMs.

Use the following values for this lab:

* `cycleDownloadUri` = TODO
* `cycleLicenseSas` = TODO
* `rsaPublicKey` = [Create](https://git-scm.com/book/en/v2/Git-on-the-Server-Generating-Your-SSH-Public-Key) your own keypair

### 3.2 Create Resource Group

Create a resource group in the region of your choice:

    az group create --name "{RESOURCE-GROUP}" --location "{REGION}"

### 3.3 Setup Networking

Build the Virtual Network and subnets. By default the vnet is named **cyclevnet**.

    az group deployment create --name "vnet_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud%20Labs/deploy-vnet.json --parameters vnet-params.json

### 3.4 Build VMs

    az group deployment create --name "vms_deployment" --resource-group "{RESOURCE-GROUP}" --template-uri https://raw.githubusercontent.com/azurebigcompute/Labs/master/CycleCloud%20Labs/deploy-vms.json --parameters vms-params.json

## 4. Configure CycleCloud Server

### 4.1 Initial Setup
To connect to the CycleCloud webserver, first retrieve the FQDN of the CycleServer VM from the Azure Portal, then browse to https://cycleserverfqdn/. The installation uses a self-signed SSL certificate which may show up with a warning in your browser.

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

For more detailed instructions, see the [installation guide](https://docs.cyclecomputing.com/installation-guide-v6.7.0/configuring_cloud_provider/masetup)





