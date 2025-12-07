Name:           hibernation-helper
Version:        0.24
Release:        1%{?dist}
Summary:        GUI tool to enable, test, and disable hibernation on Fedora

License:        GPLv3+
URL:            https://github.com/ChiefDenis/HibernationHelper
Source0:        %{name}-%{version}.tar.gz

# No architecture-specific code
BuildArch:      noarch

# Build requirements (minimal for Python app)
BuildRequires:  python3

# Runtime dependencies
Requires:       python3-pyside6
Requires:       util-linux          # for swapon, blkid
Requires:       grubby              # for kernel args
Requires:       file                # for filefrag
Requires:       systemd             # for systemctl hibernate

%description
A user-friendly GUI application to check, enable, test, and disable hibernation
on Fedora Linux. Handles both swap partitions and swap files, and integrates
seamlessly with the Plasma desktop.

%prep
%setup -q

%build
# Pure Python — nothing to build

%install
# Remove build root
rm -rf $RPM_BUILD_ROOT

# Create directory structure
mkdir -p $RPM_BUILD_ROOT/usr/bin
mkdir -p $RPM_BUILD_ROOT/usr/share/hibernation-helper
mkdir -p $RPM_BUILD_ROOT/usr/share/applications

# Install Python script
cp hibernation-helper/main.py $RPM_BUILD_ROOT/usr/share/hibernation-helper/

# Install icon (optional but recommended)
cp hibernation-helper/hibernation-helper.png $RPM_BUILD_ROOT/usr/share/hibernation-helper/

# Install launcher script
cat > $RPM_BUILD_ROOT/usr/bin/hibernation-helper << 'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/share/hibernation-helper/main.py
EOF
chmod +x $RPM_BUILD_ROOT/usr/bin/hibernation-helper

# Install desktop file
cat > $RPM_BUILD_ROOT/usr/share/applications/hibernation-helper.desktop << 'EOF'
[Desktop Entry]
Name=Hibernation Helper
Comment=Enable, test, and disable hibernation easily
Exec=hibernation-helper
Icon=/usr/share/hibernation-helper/hibernation-helper.png
Terminal=false
Type=Application
Categories=System;Settings;
StartupNotify=true
Keywords=hibernate;suspend;power;
EOF

%files
%license LICENSE
/usr/bin/hibernation-helper
/usr/share/hibernation-helper/main.py
/usr/share/hibernation-helper/hibernation-helper.png
/usr/share/applications/hibernation-helper.desktop

%changelog
* Sun Dec 07 2025 Denis <your@email.com> - 0.24-1
- Add "Disable Hibernation" and "About" dialog
- Support custom app icon
- Full hibernation lifecycle management
