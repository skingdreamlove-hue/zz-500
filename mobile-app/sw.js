var CACHE_NAME='zz500-v1';
var DATA_URLS=['zz500_factors.csv','signal.json'];
var STATIC_URLS=[
  'index.html','strategy-debug.html','review.html',
  'strategy-common.js','manifest.json',
  'vendor/papaparse.min.js'
];

self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE_NAME).then(function(cache){return cache.addAll(STATIC_URLS)}));
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
  var isData=DATA_URLS.some(function(d){return url.pathname.endsWith(d)});
  if(isData){
    e.respondWith(fetch(e.request).then(function(resp){
      var clone=resp.clone();
      caches.open(CACHE_NAME).then(function(cache){cache.put(e.request,clone)});
      return resp;
    }).catch(function(){
      return caches.match(e.request);
    }));
  }else{
    e.respondWith(caches.match(e.request).then(function(cached){
      return cached||fetch(e.request);
    }));
  }
});
