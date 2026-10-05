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
import java.util.List;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.concurrent.ArrayBlockingQueue;

public class WordCount {

  public static void main(String[] args) throws Exception {
    String fileName = args.length > 0 ? args[0] : "enwiki.xml";
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
    System.out.println("Elapsed time: " + (end - start) + "ms");

    printTopAndBottom(counts);
  }

  private static void printTopAndBottom(Map<String, Integer> counts) {
    System.out.println("Productor-Consumidor: 1 productor, 1 consumidor");
    System.out.println("Palabras distintas: " + counts.size());
    List<Map.Entry<String, Integer>> entries =
        new ArrayList<Map.Entry<String, Integer>>(counts.entrySet());
    Collections.sort(entries, new Comparator<Map.Entry<String, Integer>>() {
      public int compare(Map.Entry<String, Integer> a, Map.Entry<String, Integer> b) {
        return b.getValue().compareTo(a.getValue());
      }
    });
    System.out.println("--- 5 palabras con MAS repeticiones ---");
    for (int i = 0; i < 5 && i < entries.size(); i++)
      System.out.println((i + 1) + ". " + entries.get(i).getKey() + " = " + entries.get(i).getValue());
    System.out.println("--- 5 palabras con MENOS repeticiones ---");
    for (int i = 0; i < 5 && i < entries.size(); i++) {
      int idx = entries.size() - 1 - i;
      System.out.println((i + 1) + ". " + entries.get(idx).getKey() + " = " + entries.get(idx).getValue());
    }
  }
}
