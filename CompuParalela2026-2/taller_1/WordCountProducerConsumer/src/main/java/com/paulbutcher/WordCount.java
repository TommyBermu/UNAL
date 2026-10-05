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
import java.util.HashMap;
import java.util.concurrent.ArrayBlockingQueue;

public class WordCount {

  // Archivo de entrada (ruta hardcodeada en la raiz del taller)
  private static final String FILE_NAME =
      "../enwiki-latest-pages-articles13.xml-p10672789p11659682";

  public static void main(String[] args) throws Exception {
    String fileName = FILE_NAME;
    ArrayBlockingQueue<Page> queue = new ArrayBlockingQueue<Page>(100);
    HashMap<String, Integer> counts = new HashMap<String, Integer>();

    Thread counter = new Thread(new Counter(queue, counts));
    Thread parser = new Thread(new Parser(queue, fileName));
    long start = System.currentTimeMillis();
	
    counter.start();
    parser.start();
    parser.join();
    queue.put(new PoisonPill());
    counter.join();
    long end = System.currentTimeMillis();
    System.out.println("Archivo procesado: " + fileName);
    System.out.println("Productores: 1 | Consumidores: 1");
    System.out.println("Elapsed time: " + (end - start) + "ms");

    Results.printTopAndBottom(counts, 5);
  }
}
