# Getting started

## Umbrel

Umbrel is the easiest way to run your own squeaknode.
The following instructions are modified from here: https://github.com/getumbrel/umbrel/blob/master/apps/README.md#32-testing-on-umbrel-os-raspberry-pi-4

#### Steps

1\. SSH into your umbrel and cd into the umbrel directory

```sh
ssh umbrel@umbrel.local
cd umbrel
```

Password `moneyprintergobrrr`

2\. Switch the umbrel installation to my fork with squeaknode.

```sh
sudo scripts/update/update --repo yzernik/umbrel#master
```

3\. Install the squeaknode app

```sh
scripts/app install squeaknode
```

The app should now be accessible at http://umbrel.local:12994

Use username `umbrel` and password `moneyprintergobrrr` to sign in.

Lastly, configure your router to port forward ports `8774` and `9735` if you want your node to sell squeaks.

Configure port forwarding for port `12994` if you want to access the web interface from outside of your home.
