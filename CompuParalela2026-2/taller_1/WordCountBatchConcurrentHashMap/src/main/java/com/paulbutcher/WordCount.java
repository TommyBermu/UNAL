/***
 * Excerpted from "Seven Concurrency Models in Seven Weeks",
 * published by The Pragmatic Bookshelf.
 * Copyrights apply to this code. It may not be used to create training material, 
 * courses, books, articles, and the like. Contact us if you are in doubt.
 * We make no guarantees that this code is fit for any purpose. 
 * Visit http://www.pragmaticprogrammer.com/titles/pb7con for more book information.
***/
package com.paulbutcher;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

public class WordCount {

  // Archivo de entrada (ruta hardcodeada en la raiz del taller)
  private static final String FILE_NAME =
      "../enwiki-latest-pages-articles13.xml-p10672789p11659682";

  public static void main(String[] args) throws Exception {
    String fileName = FILE_NAME;
    int numCounters = args.length > 0 ? Integer.parseInt(args[0]) : 4;
    ArrayBlockingQueue<Page> queue = new ArrayBlockingQueue<Page>(100);
    ConcurrentHashMap<String, Integer> counts = new ConcurrentHashMap<String, Integer>();
    ExecutorService executor = Executors.newCachedThreadPool();

    for (int i = 0; i < numCounters; ++i)
      executor.execute(new Counter(queue, counts));
    Thread parser = new Thread(new Parser(queue, fileName));
    long start = System.currentTimeMillis();
    parser.start();
    parser.join();
    for (int i = 0; i < numCounters; ++i)
      queue.put(new PoisonPill());
    executor.shutdown();
    executor.awaitTermination(10L, TimeUnit.MINUTES);
    long end = System.currentTimeMillis();
    System.out.println("Archivo procesado: " + fileName);
    System.out.println("Consumidores: " + numCounters);
    System.out.println("Elapsed time: " + (end - start) + "ms");

    Results.printTopAndBottom(counts, 5);
  }
}
