package chi_test
import("net/http";"net/http/httptest";"strings";"testing";"mime";"github.com/go-chi/chi/v5";"github.com/go-chi/chi/v5/middleware")
func TestTriageQuotedCharset(t *testing.T){
 for _,ct:=range []string{"text/plain; charset=utf-8",`text/plain; charset="utf-8"`}{
 _,p,e:=mime.ParseMediaType(ct);if e!=nil||p["charset"]!="utf-8"{t.Fatal(e,p)}
 h:=middleware.ContentCharset("utf-8")(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.WriteHeader(204)})); r:=httptest.NewRequest("POST","/",strings.NewReader("x"));r.Header.Set("Content-Type",ct);w:=httptest.NewRecorder();h.ServeHTTP(w,r);t.Logf("%s -> %d",ct,w.Code);if w.Code!=204{t.Errorf("valid utf-8 charset rejected: %d",w.Code)}
 }
}
func TestTriageCompression(t *testing.T){
 h:=middleware.Compress(5)(http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){w.Header().Set("Content-Type","text/plain");w.Write([]byte(strings.Repeat("hello",200)))}))
 for _,ae:=range []string{"gzip","gzip;q=0","x-gzip"}{r:=httptest.NewRequest("GET","/",nil);r.Header.Set("Accept-Encoding",ae);w:=httptest.NewRecorder();h.ServeHTTP(w,r);t.Logf("Accept-Encoding=%q -> Content-Encoding=%q",ae,w.Header().Get("Content-Encoding"));if ae!="gzip"&&w.Header().Get("Content-Encoding")!=""{t.Errorf("rejected/nonmatching encoding used")}}
}
func TestTriageSupressPattern(t *testing.T){
 for _,enabled:=range []bool{false,true}{r:=chi.NewRouter();if enabled{r.Use(middleware.SupressNotFound(r))};r.Get("/users/{id}",func(w http.ResponseWriter,q *http.Request){w.Write([]byte(chi.RouteContext(q.Context()).RoutePattern()))});w:=httptest.NewRecorder();r.ServeHTTP(w,httptest.NewRequest("GET","/users/42",nil));t.Logf("SupressNotFound=%v -> %q",enabled,w.Body.String());if w.Body.String()!="/users/{id}"{t.Errorf("route pattern polluted")}}
}
