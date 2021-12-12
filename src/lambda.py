
# ami-0c8ae7b6508eff3f4 (64-bit Arm)
# t4g.nano
# t4g.micro (free tier eligible)


ddyn_domain = ""

userdata = """

sudo yum update -y
sudo amazon-linux-extras -y install docker
sudo service docker start
sudo usermod -a -G docker ec2-user

confdir=/tmp/openvpn
ovpnport=1194
domain={}
user=user1
dimage=damshenas/openvpn:arm64

mkdir -p $confdir
docker pull $dimage
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_genconfig -u udp://$domain
docker run -v $confdir:/etc/openvpn --rm -it -e "EASYRSA_BATCH=1" -e "EASYRSA_REQ_CN=My CN" $dimage ovpn_initpki nopass
docker run -v $confdir:/etc/openvpn -d -p $ovpnport:$ovpnport/udp --cap-add=NET_ADMIN $dimage
docker run -v $confdir:/etc/openvpn --rm -it $dimage easyrsa build-client-full $user nopass
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_getclient $user > $user.ovpn
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_listclients | grep $user

""".format(ddyn_domain)



