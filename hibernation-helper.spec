Name:           hibernation-helper
Version:        0.27
Release:        1%{?dist}
Summary:        GUI tool to enable, test, and disable hibernation on Fedora

License:        GPLv3+
URL:            https://github.com/ChiefDenis/HibernationHelper
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3

Requires:       python3-pyside6
Requires:       util-linux
Requires:       grubby
Requires:       file
Requires:       systemd

%description
A user-friendly GUI application to check, enable, test, and disable hibernation
on Fedora Linux. Handles both swap partitions and swap files, and integrates
seamlessly with the Plasma desktop.

%prep
%setup -q

# Verify version consistency
SPEC_VERSION="%{version}"
PY_VERSION=$(grep '^__version__' main.py | cut -d'"' -f2)
if [ "$SPEC_VERSION" != "$PY_VERSION" ]; then
    echo "ERROR: Version mismatch between spec ($SPEC_VERSION) and main.py ($PY_VERSION)" >&2
    exit 1
fi

# Optional: log the detected version
echo "Building Hibernation Helper version %{version}"
echo "Verified against main.py: %{real_version}"

%build
# Pure Python — nothing to build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/bin
mkdir -p $RPM_BUILD_ROOT/usr/share/hibernation-helper
mkdir -p $RPM_BUILD_ROOT/usr/share/applications

cp main.py $RPM_BUILD_ROOT/usr/share/hibernation-helper/
cp hibernation-helper.png $RPM_BUILD_ROOT/usr/share/hibernation-helper/

cat > $RPM_BUILD_ROOT/usr/bin/hibernation-helper << 'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/share/hibernation-helper/main.py
EOF
chmod +x $RPM_BUILD_ROOT/usr/bin/hibernation-helper

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
- Enforce version consistency with main.py
