var CACHE_NAME='zz500-v3';
var STATIC_ASSETS=[
  'manifest.json'
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
  if(e.request.method!=='GET')return;
  e.respondWith(
    caches.open(CACHE_NAME).then(function(cache){
      return cache.match(e.request).then(function(cached){
        var fetched=fetch(e.request).then(function(resp){
          if(resp.ok){
            var clone=resp.clone();
            cache.put(e.request,clone);
          }
          return resp;
        }).catch(function(){
          return cached||new Response('',{status:504});
        });
        return cached||fetched;
      });
    })
  );
});