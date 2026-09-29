# Podman Guide

Podman offers containerization of applications & databases.

The biggest use of containerization in my case is simply the portability.

Everything for the project can be stored within the project itself.

## Basic console command

Example:  
```
podman run -d --pod postgis --name postgres \
  -e POSTGRES_USER=gisuser \
  -e POSTGRES_PASSWORD=mypassword \
  -v ~/poddata/postgres:/var/lib/postgresql/data:Z \
  docker.io/postgis/postgis
```

`podman run` starts a new container using Podman  
`-d` runs container in *detached* mode so it doesn't block the terminal  
`--pod postgis` joins the container to an existing *pod* name `postgis`.  
Pods are groups of containers sharing the same network namespace so they can chat over `localhost`  
`--name postgres` gives this container the name `postgres` for easy reference, e.g. `podman stop postgres`  
`-e POSTGRES_USER=gis_user`, `-e POSTGRES_PASSWORD=mypassword` sets up *environment* variables in the container.   
`-v ~/poddata/postgres:/var/lib/postgresql/data:Z` mounts a *volume* for persistent data storage  
*(as containers are usually ephemeral)*  
- `~/poddata/postgres` is location of directory/volume on host machine  
- `/var/lib/postgresql/data` is where the data is stored *inside* the container  
- `:Z` is a SELinux label flag; without it, many Linux systems would block the mount.  
`docker.io/postgis/postgis` is the image pulled to use from the DockerHub; `docker.io` being the DockerHub.

## Quadlets

`Quadlets` are declarative configuration files that tell Podman's systemd generator how to run containers.



`quadlet` options:    
  
`{file-name}.{extension}`  
The name of the file tells **Podman** to create an `{extension}` object named `{file-name}`.  
The extension must be one of the following:  
- `.build` builds a container image from a Container file.  
- `.container` defines and managers a single container.  
- `.image` pulls and caches a container image.  
- `.kube` deploys containers from Kubernetes YAML using podman-kube.unit  
- `.network` creates a Podman network for containers and pods.  
- `.pod` creates a Podman pod that containers can join.  
- `.volume` ensures a named Podman volume exists (create if not exist)  
  

Relevant quadlet files for this project:  
 - `.container` for container definitions.  
 - `.pod` Pods are a group of one-or-more containers sharing same network, IPC, and namespace.  
 - `.volume` Volumes are persistent data stores for containers. Necessity for containerized storage.  
Remember, the name of the file tells **Podman** to create an `{extension}` object named `{file-name}`.  
  
Quadlets are, conceptually, two things:
- Podman configuration
- systemd unit file

NOTE: `systemd` is its own can of worms. A lot of people have strong opinions about it.
  
`[Unit]`  
`Description`  
Contains `systemd` metadata. *Technically* not required in the same way that documentation isn't *technically* required for code to run.
  
