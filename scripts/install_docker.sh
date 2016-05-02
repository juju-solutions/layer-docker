#!/bin/sh
set -e

url='https://get.docker.com/'

command_exists() {
	command -v "$@" > /dev/null 2>&1
}

echo_docker_as_nonroot() {
	if command_exists docker && [ -e /var/run/docker.sock ]; then
		(
			set -x
			$sh_c 'docker version'
		) || true
	fi
    status-set active "Docker installed and ready"
	your_user=your-user
	[ "$user" != 'root' ] && your_user="$user"
	# intentionally mixed spaces and tabs here -- tabs are stripped by "<<-EOF", spaces are kept in the output
	cat <<-EOF

	If you would like to use Docker as a non-root user, you should now consider
	adding your user to the "docker" group with something like:

	  sudo usermod -aG docker $your_user

	Remember that you will have to log out and back in for this to take effect!

	EOF
}

get_debian_dist_version() {
	dist_version=''
	case "$@" in
		8)
			dist_version="jessie"
			;;
		7)
			dist_version="wheezy"
			;;
	esac
	echo "$dist_version"
}

do_install() {
	case "$(uname -m)" in
		*64)
			;;
		*)
			cat >&2 <<-'EOF'
			Error: you are not using a 64bit platform.
			Docker currently only supports 64bit platforms.
			EOF
			exit 1
			;;
	esac

	user="$(id -un 2>/dev/null || true)"

	sh_c='sh -c'
	if [ "$user" != 'root' ]; then
		if command_exists sudo; then
			sh_c='sudo -E sh -c'
		elif command_exists su; then
			sh_c='su -c'
		else
			cat >&2 <<-'EOF'
			Error: this installer needs the ability to run commands as root.
			We are unable to find either "sudo" or "su" available to make this happen.
			EOF
			exit 1
		fi
	fi

	curl=''
	if command_exists curl; then
		curl='curl -sSL'
	elif command_exists wget; then
		curl='wget -qO-'
	elif command_exists busybox && busybox --list-modules | grep -q wget; then
		curl='busybox wget -qO-'
	fi

	# check to see which repo they are trying to install from
	repo='main'
	if [ "https://test.docker.com/" = "$url" ]; then
		repo='testing'
	elif [ "https://experimental.docker.com/" = "$url" ]; then
		repo='experimental'
	fi

	# perform some very rudimentary platform detection
	lsb_dist=''
	dist_version=''
	if command_exists lsb_release; then
		lsb_dist="$(lsb_release -si)"
	fi
	if [ -z "$lsb_dist" ] && [ -r /etc/lsb-release ]; then
		lsb_dist="$(. /etc/lsb-release && echo "$DISTRIB_ID")"
	fi
	if [ -z "$lsb_dist" ] && [ -r /etc/debian_version ]; then
		lsb_dist='debian'
	fi
	if [ -z "$lsb_dist" ]; then
		if [ -r /etc/centos-release ] || [ -r /etc/redhat-release ]; then
			lsb_dist='centos'
		fi
	fi
	if [ -z "$lsb_dist" ] && [ -r /etc/os-release ]; then
		lsb_dist="$(. /etc/os-release && echo "$ID")"
	fi

	lsb_dist="$(echo "$lsb_dist" | tr '[:upper:]' '[:lower:]')"

	case "$lsb_dist" in

		ubuntu)
			if command_exists lsb_release; then
				dist_version="$(lsb_release --codename | cut -f2)"
			fi
			if [ -z "$dist_version" ] && [ -r /etc/lsb-release ]; then
				dist_version="$(. /etc/lsb-release && echo "$DISTRIB_CODENAME")"
			fi
		;;

		debian)
			dist_version="$(cat /etc/debian_version | sed 's/\/.*//' | sed 's/\..*//')"
			case "$dist_version" in
				8)
					dist_version="jessie"
				;;
				7)
					dist_version="wheezy"
				;;
			esac
		;;

		centos)
			dist_version="$(rpm -q --whatprovides redhat-release --queryformat "%{VERSION}\n" | sed 's/\/.*//' | sed 's/\..*//')"
		;;

		*)
			if command_exists lsb_release; then
				dist_version="$(lsb_release --codename | cut -f2)"
			fi
			if [ -z "$dist_version" ] && [ -r /etc/os-release ]; then
				dist_version="$(. /etc/os-release && echo "$VERSION_ID")"
			fi
		;;


	esac

	case "$lsb_dist" in
		amzn)
			(
			set -x
			$sh_c 'sleep 3; yum -y -q install docker'
			)
			echo_docker_as_nonroot
			exit 0
			;;

		ubuntu|debian)
			export DEBIAN_FRONTEND=noninteractive
            status-set maintenance "Updating package list"
			did_apt_get_update=
			apt_get_update() {
				if [ -z "$did_apt_get_update" ]; then
					( set -x; $sh_c 'sleep 3; apt-get update' )
					did_apt_get_update=1
				fi
			}

			# aufs is preferred over devicemapper; try to ensure the driver is available.
			if ! grep -q aufs /proc/filesystems && ! $sh_c 'modprobe aufs'; then
                status-set maintenance "Installing kernel modules to support union filesystem"
				if uname -r | grep -q -- '-generic' && dpkg -l 'linux-image-*-generic' | grep -q '^ii' 2>/dev/null; then
					kern_extras="linux-image-extra-$(uname -r) linux-image-extra-virtual"

					apt_get_update
					( set -x; $sh_c 'sleep 3; apt-get install -y -q '"$kern_extras" ) || true

					if ! grep -q aufs /proc/filesystems && ! $sh_c 'modprobe aufs'; then
						echo >&2 'Warning: tried to install '"$kern_extras"' (for AUFS)'
						echo >&2 ' but we still have no AUFS.  Docker may not work. Proceeding anyways!'
						( set -x; sleep 10 )
					fi
				else
					echo >&2 'Warning: current kernel is not supported by the linux-image-extra-virtual'
					echo >&2 ' package.  We have no AUFS support.  Consider installing the packages'
					echo >&2 ' linux-image-virtual kernel and linux-image-extra-virtual for AUFS support.'
					( set -x; sleep 10 )
				fi
			fi

			# install apparmor utils if they're missing and apparmor is enabled in the kernel
			# otherwise Docker will fail to start
			if [ "$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null)" = 'Y' ]; then
                status-set maintenance "Installing apparmor security policies"
				if command -v apparmor_parser >/dev/null 2>&1; then
					echo 'apparmor is enabled in the kernel and apparmor utils were already installed'
				else
					echo 'apparmor is enabled in the kernel, but apparmor_parser missing'
					apt_get_update
					( set -x; $sh_c 'sleep 3; apt-get install -y -q apparmor' )
				fi
			fi

			if [ ! -e /usr/lib/apt/methods/https ]; then
                status-set maintenance "Installing HTTPS support"
				apt_get_update
				( set -x; $sh_c 'sleep 3; apt-get install -y -q apt-transport-https ca-certificates' )
			fi
			if [ -z "$curl" ]; then
				apt_get_update
				( set -x; $sh_c 'sleep 3; apt-get install -y -q curl ca-certificates' )
				curl='curl -sSL'
			fi
			(
            status-set maintenance "Adding PPA and installing docker"
			set -x
			$sh_c "apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D"
			$sh_c "mkdir -p /etc/apt/sources.list.d"
			$sh_c "echo deb https://apt.dockerproject.org/repo ${lsb_dist}-${dist_version} ${repo} > /etc/apt/sources.list.d/docker.list"
			$sh_c 'sleep 3; apt-get update; apt-get install -y -q docker-engine'
            )

            echo_docker_as_nonroot
			exit 0
			;;

		centos)
            status-set maintenance "Installing docker"
			$sh_c "cat >/etc/yum.repos.d/docker-${repo}.repo" <<-EOF
			[docker-${repo}-repo]
			name=Docker ${repo} Repository
			baseurl=https://yum.dockerproject.org/repo/${repo}/${lsb_dist}/${dist_version}
			enabled=1
			gpgcheck=1
			gpgkey=https://yum.dockerproject.org/gpg
			EOF
			if [ "$lsb_dist" = "fedora" ] && [ "$dist_version" -ge "22" ]; then
				(
					set -x
					$sh_c 'sleep 3; dnf -y -q install docker-engine'
				)
			else
				(
					set -x
					$sh_c 'sleep 3; yum -y -q install docker-engine'
				)
			fi
			echo_docker_as_nonroot
			exit 0
			;;
	esac

	# intentionally mixed spaces and tabs here -- tabs are stripped by "<<-'EOF'", spaces are kept in the output
	cat >&2 <<-'EOF'

	  Either your platform is not easily detectable, is not supported by this
	  installer script (yet - PRs welcome! [hack/install.sh]), or does not yet have
	  a package for Docker.  Please visit the following URL for more detailed
	  installation instructions:

	    https://docs.docker.com/en/latest/installation/

	EOF
	exit 1
}

do_install

