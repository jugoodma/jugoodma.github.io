package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"time"

	"golang.org/x/time/rate"

	"nhooyr.io/websocket"
)

type message struct {
	from int
	typ  websocket.MessageType
	msg  []byte
}

type subscriber struct {
	idx    int
	msgs   chan message
	close  chan error
	closed chan int
}

type room struct {
	// code          string
	distributor   chan message
	finisher      sync.WaitGroup
	subscribersMu sync.RWMutex
	subscribers   map[*subscriber]struct{}
	timeout       *time.Timer
	// room-unique subscriber index generator
	ticketLock sync.Mutex
	currIdx    int
	maxIdx     int
}

func (r *room) ticket() int {
	if r == nil {
		return -1 // invalid?
	}
	r.ticketLock.Lock()
	defer r.ticketLock.Unlock()
	if r.currIdx >= r.maxIdx {
		// log
		return -1
	}
	r.currIdx += 1
	return r.currIdx
}

type server struct {
	subscriberMessageBuffer int
	roomMax                 int
	publishLimiter          *rate.Limiter
	logf                    func(f string, v ...interface{})
	serveMux                http.ServeMux
	roomsMu                 sync.RWMutex
	rooms                   map[string]*room
}

func newServer() *server {
	srv := &server{
		subscriberMessageBuffer: 16,
		roomMax:                 16,
		logf:                    log.Printf,
		rooms:                   make(map[string]*room),
		publishLimiter:          rate.NewLimiter(rate.Every(time.Millisecond*100), 8),
	}
	srv.serveMux.HandleFunc("/", srv.handleRoot)
	return srv
}

func (srv *server) handleRoot(w http.ResponseWriter, r *http.Request) {
	srv.logf("received request %+v", r)
	if r.Method != http.MethodGet {
		http.Error(w, "invalid call", http.StatusMethodNotAllowed)
		return
	}
	splitPath := strings.Split(r.URL.Path[1:], "/") // we know that the path is at least "/"
	if len(splitPath) != 1 {
		http.Error(w, "invalid path", http.StatusBadRequest)
		return
	}
	roomInPath := splitPath[0]
	if len(roomInPath) != 8 {
		http.Error(w, "invalid room", http.StatusBadRequest)
		return
	}
	for _, c := range roomInPath {
		if !strings.ContainsRune("1234567890qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM", c) {
			http.Error(w, "invalid room", http.StatusBadRequest)
			return
		}
	}

	srv.logf("attempting to Accept websocket room %q", roomInPath)
	c, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		// InsecureSkipVerify: true, // TODO remove
	})
	if err != nil {
		// w has already been errored at this point
		srv.logf("error Accepting for room %q: %v", roomInPath, err)
		return
	}
	// w has been notified of 101 switch protocol
	// and the connection has been hijacked
	srv.handleSocket(c, r, roomInPath)
}

func (srv *server) handleSocket(c *websocket.Conn, r *http.Request, roomInPath string) {
	// hello
	writeTimeout(r.Context(), time.Second*10, c, message{
		from: -1,
		typ:  websocket.MessageText,
		msg:  []byte(`"ack:server"`),
	})
	// make a subscriber for this connection
	s := &subscriber{
		msgs:   make(chan message, srv.subscriberMessageBuffer),
		close:  make(chan error),  // write to this channel to close the connection -- don't close this channel -- unbuffered to ensure no write block
		closed: make(chan int, 1), // close this channel to signal this connection is closed
	}
	// close the connection when we need to
	go func() {
		err := <-s.close // block for read
		srv.logf("[%s] closing connection %d because %+v", roomInPath, s.idx, err)
		if werr, ok := err.(websocket.CloseError); ok {
			c.Close(werr.Code, werr.Reason)
		} else {
			c.Close(websocket.StatusInternalError, err.Error())
		}
		close(s.closed)
	}()

	// add subscriber to room, get room distributor
	distributor := srv.subscribe(roomInPath, s)

	errChan := make(chan error)

	// connection message reader
	go func() {
		// read all messages from this connection
		// and send to the distributor
		// should exit
		// - if the connection dies
		// - if the distributor no longer exists
		// -- invariant: if connection is still active, then the room/distributor exists
		// -- why does this hold? b/c all connections are closed before the room/distributor is killed
		//    and the room/distributor is _only_ killed after a timeout
		//    so if we're still alive, then the distributor is still alive
		srv.logf("[%s] starting reader thread", roomInPath)
		for {
			messageType, reader, err := c.Reader(r.Context()) // blocks -- todo, timeout? different context?
			// c.Reader handles reading a max byte limit
			// if the limit is hit, the connection is auto-closed
			if err != nil {
				srv.logf("[%s] err making ws reader %+v", roomInPath, err)
				errChan <- err
				break
			}
			msg, err := io.ReadAll(reader) // too big payload error is thrown here, so we can't ignore it
			if err != nil {
				srv.logf("[%s] err reading message %+v", roomInPath, err)
				errChan <- err
				break
			}
			srv.logf("[%s] received message from %d", roomInPath, s.idx)
			res, err := json.Marshal(struct {
				From int    `json:"from"`
				Data string `json:"data"`
			}{
				From: s.idx,
				Data: string(msg),
			})
			if err != nil {
				srv.logf("[%s] error marshalling message: %v", roomInPath, err)
				continue
			}
			select {
			case distributor <- message{
				from: s.idx,
				typ:  messageType,
				msg:  res,
				// perhaps we can pass the reader to the distributor
				// and then the distributor can construct a multiwriter
				// and we can io.Copy
			}: // if this blocks, then the distributor is dead
				// success -- do nothing
			default:
				srv.logf("[%s] closing conn b/c distributor blocked", roomInPath)
				errChan <- websocket.CloseError{
					Code:   websocket.StatusAbnormalClosure,
					Reason: "room is closed",
				}
				// signaling the error channel causes the connection to close
			}
		}
		srv.logf("[%s] exiting reader thread", roomInPath)
	}()

	// room subscriber
	go func() {
		// read all incoming messages the distributor gives us
		// and send to the connection
		srv.logf("[%s] starting subscriber thread", roomInPath)
		defer func() {
			srv.logf("[%s] exiting subscriber thread", roomInPath)
		}()
		// room already has this subscriber
		for {
			select {
			case msg := <-s.msgs:
				err := writeTimeout(r.Context(), time.Second*5, c, msg)
				if err != nil { // write may have timed out, or failed
					errChan <- err
					return
				}
			case _, ok := <-s.closed:
				if !ok {
					return
				}
			}
		}
	}()

	// wait
	s.close <- <-errChan // blocks

	// at this point, there was some singal to stop
	// and the connection is closed

	srv.unsubscribe(roomInPath, s)

	srv.logf("[%s] done", roomInPath)
}

// subscribe handles first-request and >first-request
// on first-request, we instantiate the new room with this subscriber in it
// on later requests, we simply add this subscriber to the room
// this is in a function to ensure we unlock the room
func (srv *server) subscribe(roomInPath string, s *subscriber) chan message {
	srv.roomsMu.Lock()
	defer srv.roomsMu.Unlock()
	// - is this a new room?
	if foundRoom, found := srv.rooms[roomInPath]; !found {
		// first websocket to this room, so we need to create the room
		srv.logf("constructing new room for %q", roomInPath)
		room := &room{
			// code:        roomInPath,
			distributor: make(chan message),
			finisher:    sync.WaitGroup{},
			subscribers: make(map[*subscriber]struct{}),
			timeout:     time.NewTimer(10 * time.Minute),
			currIdx:     -1,
			maxIdx:      srv.roomMax,
		}
		s.idx = room.ticket()            // give this connection's subscriber a ticket -- shouldn't fail
		room.subscribersMu.Lock()        // technically not necessary
		room.subscribers[s] = struct{}{} // place this connection as an initial subscriber
		room.finisher.Add(1)             // increment the WG
		room.subscribersMu.Unlock()      // defer?
		srv.rooms[roomInPath] = room     // place room in the server
		// make done signal
		finish := make(chan int)
		go func() {
			room.finisher.Wait() // block until all subscribers have died
			finish <- 1
		}()
		// start distribution routine
		go func() {
			// take all distributor messages
			// and send to each subscriber
			//
			// do this until the timeout passes
			// or until all subscribers are deleted
			defer func() {
				srv.logf("[%s] closing all connections", roomInPath)
				// close all connections before cleaning up resources
				for sub := range room.subscribers {
					sub.close <- websocket.CloseError{
						Code:   websocket.StatusGoingAway,
						Reason: "room is closed",
					} // shouldn't block
				}
				// wait for all subscribers to close
				for sub := range room.subscribers {
					for range sub.closed {
					}
				}
				srv.logf("[%s] all subscribers closed", roomInPath)
				// now we can clean up resources
				// this only deadlocks if the first lock, at the top of this subscribe function, never
				// unlocks. but, the unlock is deferred, so it'll always unlock
				// _furthermore_, _this_ lock is in a separate go-routine
				srv.roomsMu.Lock()
				defer srv.roomsMu.Unlock() // if, for some reason, the delete panics
				delete(srv.rooms, roomInPath)
			}()
			keepGoing := true
			for keepGoing {
				select {
				case <-room.timeout.C:
					srv.logf("[%s] room timed out", roomInPath)
					return
				case msg := <-room.distributor:
					srv.logf("[%s] distributing message from %d to %d other subscribers", roomInPath, msg.from, len(room.subscribers)-1)
					room.subscribersMu.RLock()
					for sub := range room.subscribers {
						if sub.idx == msg.from { // skip echoing message back to the sender
							continue
						}
						select { // test for slow connections
						case sub.msgs <- msg:
						default:
							sub.close <- websocket.CloseError{
								Code:   websocket.StatusPolicyViolation,
								Reason: "connection too slow",
							} // shouldn't block
						}
					}
					room.subscribersMu.RUnlock()
				case <-finish:
					// close(finish)
					keepGoing = false
				}
			}
			srv.logf("[%s] room has no more subscribers", roomInPath)
		}()
		return room.distributor
	} else {
		s.idx = foundRoom.ticket() // give this connection's subscriber a ticket
		if s.idx == -1 {
			s.close <- websocket.CloseError{
				Code:   websocket.StatusPolicyViolation,
				Reason: "too many connections",
			}
			return nil
		}
		foundRoom.subscribersMu.Lock() // necessary
		foundRoom.subscribers[s] = struct{}{}
		foundRoom.finisher.Add(1)
		foundRoom.subscribersMu.Unlock()
		return foundRoom.distributor
	}
}

func (srv *server) unsubscribe(roomInPath string, s *subscriber) {
	// remove this subscriber from the room
	srv.roomsMu.RLock()
	defer srv.roomsMu.RUnlock()
	room := srv.rooms[roomInPath] // if not ok, invalid?
	room.subscribersMu.Lock()
	defer room.subscribersMu.Unlock()
	delete(room.subscribers, s)
	room.finisher.Done()
}

func (srv *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	srv.serveMux.ServeHTTP(w, r)
}

func writeTimeout(ctx context.Context, timeout time.Duration, c *websocket.Conn, msg message) error {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	return c.Write(ctx, msg.typ, msg.msg)
}

func main() {
	l, err := net.Listen("tcp", ":4201")
	if err != nil {
		panic(err)
	}
	log.Printf("listening on http://%v", l.Addr())

	s := &http.Server{
		Handler:      newServer(),
		ReadTimeout:  time.Second * 10,
		WriteTimeout: time.Second * 10,
	}
	errc := make(chan error, 1)
	go func() {
		errc <- s.Serve(l)
	}()

	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, os.Interrupt)
	select {
	case err := <-errc:
		log.Printf("failed to serve: %v", err)
	case sig := <-sigs:
		log.Printf("terminating: %v", sig)
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Second*10)
	defer cancel()

	s.Shutdown(ctx)
}
