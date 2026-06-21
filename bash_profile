if [ "$(tty)" = "/dev/tty1" ]; then
    clear
    sleep 3

    # esperar a que VT esté realmente activo
    while ! fgconsole 1>/dev/null 2>&1; do
        sleep 1
    done

    python3 /opt/akerbar-controller/akerbar-display.py
fi