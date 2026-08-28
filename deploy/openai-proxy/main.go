// openai-proxy: a CONNECT proxy that will only reach an allowlisted set of hosts.
//
// Why this exists: kidscomp (the Pi the kids use YouMon on) should be able to
// reach the OpenAI API and nothing else. Doing that with firewall rules does not
// work -- api.openai.com sits behind Cloudflare, so its addresses rotate and are
// shared with most of the internet. An IP allowlist is therefore both leaky and
// prone to breaking without warning.
//
// A CONNECT proxy sidesteps the problem. An HTTPS client asks for a host by
// name ("CONNECT api.openai.com:443") before any TLS happens, so the hostname is
// there in plaintext to check. Nothing is decrypted and no certificates are
// involved: once a request is allowed, bytes are copied in both directions and
// the TLS session is strictly between the client and OpenAI. The proxy resolves
// the hostname itself, so a client cannot talk its way to somewhere else.
package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"
)

var (
	listen  = flag.String("listen", "0.0.0.0:3128", "address to listen on")
	allowed = flag.String("allow", "api.openai.com", "comma-separated allowlist of exact hostnames")
	clients = flag.String("clients", "", "comma-separated client IPs permitted to use the proxy (empty = any)")
	dialTO  = flag.Duration("dial-timeout", 15*time.Second, "upstream dial timeout")
	idleTO  = flag.Duration("idle-timeout", 5*time.Minute, "close a tunnel after this long with no traffic")
)

type proxy struct {
	hosts   map[string]bool
	clients map[string]bool
}

func (p *proxy) clientAllowed(remote string) bool {
	if len(p.clients) == 0 {
		return true
	}
	host, _, err := net.SplitHostPort(remote)
	if err != nil {
		return false
	}
	return p.clients[host]
}

func (p *proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if !p.clientAllowed(r.RemoteAddr) {
		log.Printf("DENY client %s", r.RemoteAddr)
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	// Only CONNECT. Plain HTTP proxying is refused outright: it would let a
	// client fetch arbitrary cleartext URLs, which is the thing being prevented.
	if r.Method != http.MethodConnect {
		log.Printf("DENY %s %s from %s (only CONNECT is served)", r.Method, r.Host, r.RemoteAddr)
		http.Error(w, "this proxy serves CONNECT only", http.StatusMethodNotAllowed)
		return
	}

	host, port, err := net.SplitHostPort(r.Host)
	if err != nil {
		http.Error(w, "bad target", http.StatusBadRequest)
		return
	}
	if port != "443" {
		log.Printf("DENY %s from %s (port %s, only 443)", r.Host, r.RemoteAddr, port)
		http.Error(w, "only port 443", http.StatusForbidden)
		return
	}
	if !p.hosts[strings.ToLower(host)] {
		log.Printf("DENY %s from %s (host not allowlisted)", r.Host, r.RemoteAddr)
		http.Error(w, "host not allowed", http.StatusForbidden)
		return
	}

	// Resolution happens here, on the proxy, from the allowlisted name.
	upstream, err := net.DialTimeout("tcp", net.JoinHostPort(host, port), *dialTO)
	if err != nil {
		log.Printf("FAIL %s from %s: %v", r.Host, r.RemoteAddr, err)
		http.Error(w, "upstream unreachable", http.StatusBadGateway)
		return
	}
	defer upstream.Close()

	hj, ok := w.(http.Hijacker)
	if !ok {
		http.Error(w, "hijack unsupported", http.StatusInternalServerError)
		return
	}
	client, _, err := hj.Hijack()
	if err != nil {
		return
	}
	defer client.Close()

	if _, err := client.Write([]byte("HTTP/1.1 200 Connection established\r\n\r\n")); err != nil {
		return
	}
	log.Printf("ALLOW %s from %s", r.Host, r.RemoteAddr)

	var wg sync.WaitGroup
	wg.Add(2)
	pipe := func(dst, src net.Conn) {
		defer wg.Done()
		buf := make([]byte, 32*1024)
		for {
			_ = src.SetReadDeadline(time.Now().Add(*idleTO))
			n, err := src.Read(buf)
			if n > 0 {
				_ = dst.SetWriteDeadline(time.Now().Add(*idleTO))
				if _, werr := dst.Write(buf[:n]); werr != nil {
					break
				}
			}
			if err != nil {
				break
			}
		}
		// Unblock the other direction rather than waiting out the idle timeout.
		if c, ok := dst.(*net.TCPConn); ok {
			_ = c.CloseWrite()
		}
	}
	go pipe(upstream, client)
	go pipe(client, upstream)
	wg.Wait()
}

func set(csv string) map[string]bool {
	m := map[string]bool{}
	for _, s := range strings.Split(csv, ",") {
		if s = strings.ToLower(strings.TrimSpace(s)); s != "" {
			m[s] = true
		}
	}
	return m
}

func main() {
	flag.Parse()
	p := &proxy{hosts: set(*allowed), clients: set(*clients)}
	log.Printf("openai-proxy listening on %s", *listen)
	log.Printf("  allowed hosts:   %s", *allowed)
	if *clients == "" {
		log.Printf("  allowed clients: ANY (restrict with -clients)")
	} else {
		log.Printf("  allowed clients: %s", *clients)
	}
	srv := &http.Server{
		Addr:              *listen,
		Handler:           p,
		ReadHeaderTimeout: 10 * time.Second,
	}
	log.Fatal(srv.ListenAndServe())
}
