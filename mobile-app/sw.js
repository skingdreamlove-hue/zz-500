var CACHE_NAME='zz500-v2';
var HTML_FILES=['index.html','strategy-debug.html','review.html'];
var STATIC_ASSETS=[
  'strategy-common.js','manifest.json',
  'vendor/papaparse.min.js'
];

self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE_NAME).then(function(cache){
    return cache.addAll(STATIC_ASSETS);
  }));
  self.skipWaiting();
});

self.addEventListener('activate',function(e){
  e.waitUntil(caches.keys().then(function(names){
    return Promise.all(names.filter(function(n){return n!==CACHE_NAME}).map(function(n){return caches.delete(n)}));
  }));
  self.clients.claim();
});

self.addEventListener('fetch',function(e){
  var url=new URL(e.request.url);
  var isHtml=HTML_FILES.some(function(f){return url.pathname.endsWith(f)});

  if(isHtml){
    e.respondWith(
      fetch(e.request).then(function(resp){
        if(resp.ok){
          var clone=resp.clone();
          caches.open(CACHE_NAME).then(function(cache){cache.put(e.request,clone)});
        }
        return resp;
      }).catch(function(){
        return caches.match(e.request);
      })
    );
  }else{
    e.respondWith(
      caches.match(e.request).then(function(cached){
        var fetcher=fetch(e.request).then(function(resp){
          if(resp.ok){
            var clone=resp.clone();
            caches.open(CACHE_NAME).then(function(cache){cache.put(e.request,clone)});
          }
          return resp;
        });
        return cached||fetcher;
      })
    );
  }
});