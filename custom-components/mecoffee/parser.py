def parse_packet(packet):

    parts = packet.split(",")

    if not parts:
        return {}

    t = parts[0]

    if t == "tmp":
        return {
            "target_temp": float(parts[2]),
            "temperature": float(parts[3])
        }

    if t == "prs":
        return {
            "pressure": int(parts[1])
        }

    if t == "sht":
        return {
            "shot_time": int(parts[1])
        }

    if t == "sta":
        return {
            "heater": bool(int(parts[1])),
            "pump": bool(int(parts[2]))
        }

    return {}
