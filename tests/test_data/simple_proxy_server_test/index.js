const express = require('express');
const request = require('request');
const path = require('path');
const app = express();
// Set up report port
const API_URL = 'http://127.0.0.1:8000/' // ADR server location (port using docker default port 8000)

app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  next();
});

// get core report contents
app.get('/report/:guid/:query?', (req, res) => {
  console.log(req.params.guid, req.params.query)
  request(
    { url: `${API_URL}/reports/report_display/?report_table_length=10&view=${req.params.guid}&usemenus=on&dpi=120&pwidth=12.80&query=${req.params.query || ""}` },
    (error, response, body) => {
      if (error || response.statusCode !== 200) {
        return res.status(500).json({ type: 'error', message: error });
      }
      res.set('Content-Type', 'text/html');
      res.send(Buffer.from(body));
    }
  );
});

// get static directory assets
app.get('/static*', (req, res) => {
  request(
    {
      url: `${API_URL}${req.originalUrl}`,
      encoding: null
     },

    (error, response, body) => {
      if (error || response.statusCode !== 200) {
        return res.status(500).json({ type: 'error', message: error });
      }

      if(req.originalUrl.match('.css$')){
        res.set('Content-Type', 'text/css');
        res.send(Buffer.from(body));

      }else if(req.originalUrl.match('.js$')){
        res.set('Content-Type', 'text/js');
        res.send(Buffer.from(body));

      }else if(req.originalUrl.match('.woff$')){
        res.set('Content-Type', 'font/woff');
        res.send(Buffer.from(response.body));

      }else if(req.originalUrl.match('.woff2$')){
        res.set('Content-Type', 'font/woff2');
        res.send(Buffer.from(response.body));

      }else if(req.originalUrl.match('.tff$')){
        res.set('Content-Type', 'font/ttf');
        res.send(Buffer.from(response.body));

      }else if(req.originalUrl.match('.png$')){
        // res.redirect(`${API_URL}${req.originalUrl}`);
        res.set('Content-Type', 'image/jpeg');
        res.send(response.body);

      }else{
        console.log(res)
        res.send(Buffer.from(body));
      }
    }
  );
});

// get media directory assets
app.get('/media*', (req, res) => {
  request(
    {
      url: `${API_URL}${req.originalUrl}`,
      encoding: null
    },
    (error, response, body) => {
      if (error || response.statusCode !== 200) {
        return res.status(500).json({ type: 'error', message: error });
      }

      if(req.originalUrl.match('.png$')){
        res.set('Content-Type', 'image/jpeg');
        res.send(response.body);

      }else if(req.originalUrl.match('.js$')){
        res.set('Content-Type', 'text/js');
        res.send(Buffer.from(body));

      }else{
        res.send(Buffer.from(body));
      }
    }
  );
});

// =================================================================================================
// You OWN APP
app.get('/', function(request, response){
  // send file to the server directory (in pyadr test, it's "/simple_proxy_server_test/")
  response.sendFile(path.join(__dirname, '../simple_proxy_server_test', 'index.html'));
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`listening on ${PORT}`));