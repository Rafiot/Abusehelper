from idiokit import threado
from abusehelper.core import utils, cymru, bot, events

class DShieldBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=False)

    def augment(self):
        if not self.use_cymru_whois:
            return bot.PollingBot.augment(self)
        return cymru.CymruWhois()

    def feed_keys(self, asns, **keys):
        return map(str, asns)

    def room_keys(self, asns, **keys):
        return map(str, asns)

    def event_keys(self, event):
        return list(event.values("asn"))

    @threado.stream
    def poll(inner, self, asn, url="http://dshield.org/asdetailsascii.html"):
        url += "?as=%s" % asn

        self.log.info("ASN%s: downloading", asn)
        try:
            info, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, fuf:
            self.log.error("ASN%s: downloading failed: %r", asn, fuf)
            return
        self.log.info("ASN%s: downloaded", asn)

        charset = info.get_param("charset")
        columns = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]
        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        yield inner.sub(utils.csv_to_events(filtered,
                                            delimiter="\t", 
                                            columns=columns,
                                            charset=charset)
                        | self.normalize(asn))

    @threado.stream
    def normalize(inner, self, asn):
        while True:
            event = yield inner

            ips = list(event.values("ip"))
            event.clear("ip")
            for ip in ips:
                try:
                    ip = ".".join(map(str, map(int, ip.split("."))))
                except ValueError:
                    pass
                event.add("ip", ip)
            
            if self.use_cymru_whois:
                event.add("dshield asn", asn)
            else:
                event.add("asn", asn)
            event.add("feed", "dshield")

            inner.send(event)

if __name__ == "__main__":
    DShieldBot.from_command_line().execute()
